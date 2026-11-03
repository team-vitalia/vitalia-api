"""
PRUEBA - Registro público de pacientes, CURP, RFC y seguridad del alta de usuarios.

Comprueba que:
  - El registro público funciona SIN sesión y solo crea pacientes.
  - El rol lo fija el servidor: no se puede escalar privilegios enviando un rol.
  - Correo y CURP se validan, se normalizan y no se pueden duplicar
    (verificación previa + respaldo ante la restricción UNIQUE de la base de datos).
  - El alta administrativa (POST /api/usuarios/) exige sesión y permisos.

No requiere MySQL: usa una base de datos simulada.

Ejecutar:  pytest tests/test_registro_paciente.py -v
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import get_current_user
from app.core.validaciones import (
    componer_apellido,
    normalizar_curp,
    validar_curp,
    validar_nombre_persona,
    validar_rfc,
)
from app.database.connection import get_db
from app.main import app
from app.models.doctor import Doctor
from app.models.paciente import Paciente
from app.models.role import Role
from app.models.usuario import Usuario

client = TestClient(app)

CURP_VALIDA = "LOGM000510MDFPRRA3"
OTRA_CURP = "GODE561231HDFRRN04"
URL_REGISTRO = "/api/auth/registro"


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def crear_db(correo_existente=None, curp_existente=None, rol_paciente_activo=True):
    """Base de datos simulada con los resultados que necesita el registro."""
    db = MagicMock()
    rol = (
        SimpleNamespace(id_PK=3, nombre="Paciente", esta_activo=True)
        if rol_paciente_activo
        else None
    )

    def query_falsa(modelo):
        consulta = MagicMock()

        def filter_falsa(*args, **kwargs):
            filtro = MagicMock()
            if modelo is Usuario:
                filtro.first.return_value = correo_existente
            elif modelo is Role:
                filtro.first.return_value = rol
            elif modelo is Paciente:
                filtro.first.return_value = curp_existente
            else:
                filtro.first.return_value = None
            return filtro

        consulta.filter.side_effect = filter_falsa
        return consulta

    db.query.side_effect = query_falsa

    def flush_falsa():
        for llamada in db.add.call_args_list:
            objeto = llamada.args[0]
            if isinstance(objeto, Usuario):
                objeto.id_PK = 77

    db.flush.side_effect = flush_falsa
    db.refresh.side_effect = lambda objeto: None
    app.dependency_overrides[get_db] = lambda: db
    return db


def datos_registro(**extra):
    base = {
        "nombre": "María Fernanda",
        "apellido_paterno": "López",
        "apellido_materno": "Reyes",
        "curp": CURP_VALIDA,
        "correo_electronico": "maria@correo.com",
        "password": "Segura1234",
    }
    base.update(extra)
    return base


def registrar(db_kwargs=None, **extra):
    db = crear_db(**(db_kwargs or {}))
    with patch("app.routers.auth.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(URL_REGISTRO, json=datos_registro(**extra))
    return respuesta, db


def agregados(db):
    return [llamada.args[0] for llamada in db.add.call_args_list]


# ============================================================ REGISTRO PÚBLICO
def test_registro_publico_funciona_sin_sesion_y_crea_paciente():
    # No se sobreescribe get_current_user: la ruta no debe pedir token.
    respuesta, db = registrar()

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert "iniciar sesión" in cuerpo["mensaje"].lower()
    assert cuerpo["usuario"]["correo_electronico"] == "maria@correo.com"
    assert "password" not in cuerpo["usuario"]
    assert "hash_contrasena" not in cuerpo["usuario"]

    usuario = next(o for o in agregados(db) if isinstance(o, Usuario))
    paciente = next(o for o in agregados(db) if isinstance(o, Paciente))

    # El rol lo asigna el servidor.
    assert usuario.rol_id_FK == 3
    assert usuario.estado == "activo"
    assert usuario.hash_contrasena == "hash-falso"
    assert usuario.apellido_paterno == "López"
    assert usuario.apellido_materno == "Reyes"

    assert paciente.usuario_id_FK == 77
    assert paciente.curp == CURP_VALIDA
    assert paciente.apellido_paterno == "López"
    assert paciente.apellido_materno == "Reyes"
    # Columna heredada: apellido completo para citas, recordatorios, etc.
    assert paciente.apellido == "López Reyes"

    assert db.commit.call_count == 1


def test_registro_publico_no_acepta_rol_enviado_por_el_cliente():
    respuesta, db = registrar(rol_id_FK=1)

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0
    assert agregados(db) == []


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("rol_id_FK", 2),
        ("rol", "Administrador"),
        ("estado", "activo"),
        ("rfc", "GODE561231AB1"),
        ("numero_licencia", "LIC-1"),
        ("especialidad_ids", [1]),
    ],
)
def test_registro_publico_rechaza_campos_ajenos_al_paciente(campo, valor):
    respuesta, db = registrar(**{campo: valor})

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


def test_registro_publico_normaliza_correo_y_curp():
    respuesta, db = registrar(
        correo_electronico="  Maria@Correo.COM ",
        curp=" logm000510mdfprra3 ",
    )

    assert respuesta.status_code == 201, respuesta.text
    usuario = next(o for o in agregados(db) if isinstance(o, Usuario))
    paciente = next(o for o in agregados(db) if isinstance(o, Paciente))

    assert usuario.correo_electronico == "maria@correo.com"
    assert paciente.correo_electronico == "maria@correo.com"
    assert paciente.curp == CURP_VALIDA


def test_registro_publico_apellido_materno_es_opcional():
    respuesta, db = registrar(apellido_materno="")

    assert respuesta.status_code == 201, respuesta.text
    paciente = next(o for o in agregados(db) if isinstance(o, Paciente))
    assert paciente.apellido_materno is None
    assert paciente.apellido == "López"


@pytest.mark.parametrize("campo", ["nombre", "apellido_paterno", "curp", "correo_electronico", "password"])
def test_registro_publico_campos_obligatorios(campo):
    datos = datos_registro()
    del datos[campo]
    db = crear_db()

    respuesta = client.post(URL_REGISTRO, json=datos)

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


@pytest.mark.parametrize("campo", ["nombre", "apellido_paterno"])
def test_registro_publico_rechaza_campos_vacios(campo):
    respuesta, db = registrar(**{campo: "   "})

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


def test_registro_publico_rechaza_nombres_con_numeros():
    respuesta, _ = registrar(nombre="Mar1a")
    assert respuesta.status_code == 422


def test_registro_publico_contrasena_corta_422():
    respuesta, db = registrar(password="corta")

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


# ----------------------------------------------------------------- correo
@pytest.mark.parametrize("correo", ["no-es-correo", "a@b", "sin-arroba.com", ""])
def test_registro_publico_correo_invalido_422(correo):
    respuesta, db = registrar(correo_electronico=correo)

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


def test_registro_publico_correo_duplicado_400_con_mensaje_claro():
    existente = SimpleNamespace(id_PK=5, correo_electronico="maria@correo.com")

    respuesta, db = registrar(db_kwargs={"correo_existente": existente})

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Ya existe un usuario con ese correo electrónico"
    assert db.commit.call_count == 0


# ------------------------------------------------------------------- CURP
@pytest.mark.parametrize(
    "curp",
    [
        "LOGM000510MDFPRRA",       # 17 caracteres
        "LOGM000510MDFPRRA33",     # 19 caracteres
        "1OGM000510MDFPRRA3",      # empieza con dígito
        "LOGM001310MDFPRRA3",      # mes 13
        "LOGM000510ZDFPRRA3",      # sexo inválido (solo H, M o X)
        "LOGM000510MXXPRRA3",      # entidad inexistente
        "LOGM000230MDFPRRA3",      # 30 de febrero
        "",
    ],
)
def test_registro_publico_curp_invalida_422(curp):
    respuesta, db = registrar(curp=curp)

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


def test_registro_publico_curp_duplicada_409_con_mensaje_claro():
    existente = SimpleNamespace(id_PK=9, curp=CURP_VALIDA)

    respuesta, db = registrar(db_kwargs={"curp_existente": existente})

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Esta CURP ya está registrada"
    # No queda nada a medias: se revierte la transacción.
    assert db.commit.call_count == 0
    assert db.rollback.call_count == 1


def test_registro_publico_unique_de_base_de_datos_respalda_la_curp():
    """Dos solicitudes simultáneas: la 2.ª pasa la verificación pero choca con UNIQUE."""
    db = crear_db()
    db.commit.side_effect = IntegrityError(
        "INSERT INTO pacientes ...",
        {},
        Exception("(1062, \"Duplicate entry 'LOGM000510MDFPRRA3' for key 'pacientes.uq_pacientes_curp'\")"),
    )

    with patch("app.routers.auth.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(URL_REGISTRO, json=datos_registro())

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Esta CURP ya está registrada"
    assert db.rollback.call_count == 1


def test_registro_publico_unique_de_correo_respalda_el_correo():
    db = crear_db()
    db.commit.side_effect = IntegrityError(
        "INSERT INTO usuarios ...",
        {},
        Exception("(1062, \"Duplicate entry 'maria@correo.com' for key 'usuarios.correo_electronico'\")"),
    )

    with patch("app.routers.auth.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(URL_REGISTRO, json=datos_registro())

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Ya existe un usuario con ese correo electrónico"


def test_registro_publico_rol_paciente_inactivo_400():
    respuesta, db = registrar(db_kwargs={"rol_paciente_activo": False})

    assert respuesta.status_code == 400
    assert db.commit.call_count == 0


def test_registro_publico_error_inesperado_no_expone_detalles():
    db = crear_db()
    db.commit.side_effect = RuntimeError("fallo interno con datos sensibles")

    with patch("app.routers.auth.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(URL_REGISTRO, json=datos_registro())

    assert respuesta.status_code == 500
    assert "sensibles" not in respuesta.text
    assert db.rollback.call_count == 1


# ================================= ALTA ADMINISTRATIVA: ahora exige sesión y rol
def datos_admin(**extra):
    base = {
        "nombre": "Ana",
        "apellido_paterno": "Pérez",
        "correo_electronico": "ana@vitalia.com",
        "password": "Segura1234",
        "rol_id_FK": 4,
    }
    base.update(extra)
    return base


def entrar_como(rol_id, db=None):
    usuario = SimpleNamespace(
        id_PK=1, nombre="Actor", correo_electronico="actor@vitalia.com",
        rol_id_FK=rol_id, estado="activo",
    )
    app.dependency_overrides[get_current_user] = lambda: usuario
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db


def test_alta_administrativa_sin_token_401():
    """Antes este endpoint estaba abierto: ahora cualquiera sin sesión es rechazado."""
    respuesta = client.post("/api/usuarios/", json=datos_admin(rol_id_FK=1))

    assert respuesta.status_code == 401


@pytest.mark.parametrize("rol_actor", [2, 3, 4])
def test_alta_administrativa_prohibida_para_doctor_paciente_y_recepcion(rol_actor):
    db = crear_db()
    entrar_como(rol_actor, db)

    respuesta = client.post("/api/usuarios/", json=datos_admin())

    assert respuesta.status_code == 403
    assert db.commit.call_count == 0


def test_admin_crea_paciente_con_curp_y_apellidos():
    db = crear_db()
    entrar_como(1, db)

    with patch("app.routers.usuarios.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(
            "/api/usuarios/",
            json=datos_admin(
                rol_id_FK=3,
                apellido_materno="Gómez",
                curp=CURP_VALIDA.lower(),
            ),
        )

    assert respuesta.status_code == 201, respuesta.text
    paciente = next(o for o in agregados(db) if isinstance(o, Paciente))
    assert paciente.curp == CURP_VALIDA
    assert paciente.apellido == "Pérez Gómez"


def test_admin_paciente_sin_curp_400():
    db = crear_db()
    entrar_como(1, db)

    respuesta = client.post("/api/usuarios/", json=datos_admin(rol_id_FK=3))

    assert respuesta.status_code == 400
    assert "curp" in respuesta.json()["detail"].lower()
    assert db.commit.call_count == 0
    assert db.rollback.call_count == 1


def test_admin_paciente_con_curp_duplicada_409():
    db = crear_db(curp_existente=SimpleNamespace(id_PK=2, curp=CURP_VALIDA))
    entrar_como(1, db)

    respuesta = client.post("/api/usuarios/", json=datos_admin(rol_id_FK=3, curp=CURP_VALIDA))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Esta CURP ya está registrada"
    assert db.commit.call_count == 0


def test_admin_doctor_guarda_rfc_normalizado():
    db = crear_db()
    # El rol Doctor debe existir en la base simulada.
    base_query = db.query.side_effect

    def query_con_rol_doctor(modelo):
        consulta = base_query(modelo)
        if modelo is Role:
            consulta.filter.side_effect = lambda *a, **k: MagicMock(
                first=MagicMock(return_value=SimpleNamespace(id_PK=2, nombre="Doctor", esta_activo=True))
            )
        return consulta

    db.query.side_effect = query_con_rol_doctor
    entrar_como(1, db)

    with patch("app.routers.usuarios.generar_hash_password", return_value="hash-falso"):
        respuesta = client.post(
            "/api/usuarios/",
            json=datos_admin(rol_id_FK=2, rfc="gode-561231-ab1", numero_licencia="LIC-9"),
        )

    assert respuesta.status_code == 201, respuesta.text
    doctor = next(o for o in agregados(db) if isinstance(o, Doctor))
    assert doctor.rfc == "GODE561231AB1"


def test_admin_doctor_rfc_invalido_422():
    db = crear_db()
    entrar_como(1, db)

    respuesta = client.post("/api/usuarios/", json=datos_admin(rol_id_FK=2, rfc="12345"))

    assert respuesta.status_code == 422
    assert db.commit.call_count == 0


# ======================================================== VALIDADORES (unitarios)
@pytest.mark.parametrize("curp", [CURP_VALIDA, OTRA_CURP, "LOPM000229MMCPRRA9"])
def test_validar_curp_acepta_curps_correctas(curp):
    assert validar_curp(curp) == curp


def test_validar_curp_normaliza_mayusculas_y_espacios():
    assert validar_curp(" gode 5612 31hd frrn04 ") == OTRA_CURP
    assert normalizar_curp("gode-561231-hdfrrn04") == OTRA_CURP


@pytest.mark.parametrize(
    "curp,fragmento",
    [
        ("ABC", "18 caracteres"),
        ("GODE561331HDFRRN04", "formato"),
        ("LOPM000229MMCPRR09", "fecha"),   # 29-feb-1900 no existe
        ("GODE561231HDFRRN0!", "formato"),
    ],
)
def test_validar_curp_rechaza_con_mensaje_claro(curp, fragmento):
    with pytest.raises(ValueError) as error:
        validar_curp(curp)
    assert fragmento in str(error.value).lower()


@pytest.mark.parametrize("rfc", ["GODE561231AB1", "gode-561231-ab1", "XAXX010101000", "ABC010101AB1"])
def test_validar_rfc_acepta_12_o_13_caracteres(rfc):
    assert validar_rfc(rfc) in {"GODE561231AB1", "XAXX010101000", "ABC010101AB1"}


@pytest.mark.parametrize("rfc", ["", "ABC", "GODE56123", "GODE561231AB12", "1ODE561231AB1"])
def test_validar_rfc_rechaza_formatos_invalidos(rfc):
    with pytest.raises(ValueError):
        validar_rfc(rfc)


@pytest.mark.parametrize("nombre", ["María José", "O'Brien", "Ana-Lucía", "Dr. Juan Pérez", "de la Cruz"])
def test_validar_nombre_acepta_nombres_reales(nombre):
    assert validar_nombre_persona(nombre, "El nombre") == nombre


@pytest.mark.parametrize("nombre", ["", "   ", "J0hn", "Ana_", "-Ana", "Ana@"])
def test_validar_nombre_rechaza_valores_invalidos(nombre):
    with pytest.raises(ValueError):
        validar_nombre_persona(nombre, "El nombre")


def test_validar_nombre_colapsa_espacios():
    assert validar_nombre_persona("  Juan   Carlos ", "El nombre") == "Juan Carlos"


def test_componer_apellido():
    assert componer_apellido("López", "Reyes") == "López Reyes"
    assert componer_apellido("López", None) == "López"
    assert componer_apellido(None, None) == ""
