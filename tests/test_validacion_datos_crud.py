"""
PRUEBA 20 - Validación de datos en creación, edición y eliminación.

Verifica que la API acepte datos correctos y rechace los incorrectos de forma
clara (códigos 4xx con mensaje), para que la interfaz muestre lo mismo que se
guardó en la base de datos. No requiere MySQL: usa una base de datos simulada.

Ejecutar:  pytest tests/test_validacion_datos_crud.py -v

Autor: 2024-06-10 - Vitalia S.A. - Equipo de Desarrollo - Guadarrama Hernandez Jose Luis

"""
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db

client = TestClient(app)

ADMIN, DOCTOR, PACIENTE, RECEPCION, COORDINADOR = 1, 2, 3, 4, 5
NOMBRE_ROL = {1: "Administrador", 2: "Doctor", 3: "Paciente", 4: "Recepcionista", 5: "Coordinador"}


class _Consulta:
    """Simula la cadena query().filter().order_by()... de SQLAlchemy."""

    def __init__(self, valor):
        self.valor = valor

    def __getattr__(self, nombre):
        if nombre in ("filter", "order_by", "options", "join", "limit", "offset"):
            return lambda *a, **k: self
        raise AttributeError(nombre)

    def first(self):
        if isinstance(self.valor, list):
            return self.valor[0] if self.valor else None
        return self.valor

    def all(self):
        if self.valor is None:
            return []
        return self.valor if isinstance(self.valor, list) else [self.valor]

    def delete(self):
        return 0

    def count(self):
        return len(self.all())


class FakeDB:
    """Base de datos falsa: no necesita MySQL. `resultados` mapea Modelo -> valor."""

    def __init__(self, resultados=None):
        self.resultados = resultados or {}
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def _clave(self, modelo):
        return getattr(modelo, "class_", modelo)

    def query(self, *modelos):
        return _Consulta(self.resultados.get(self._clave(modelos[0])))

    def get(self, modelo, _id):
        return self.resultados.get(modelo)

    def add(self, obj):
        if hasattr(obj, "id_PK") and getattr(obj, "id_PK", None) is None:
            obj.id_PK = len(self.agregados) + 1
        self.agregados.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        pass

    def delete(self, obj):
        pass


def usuario(rol_id, id_usuario=1, nombre="Usuario"):
    return SimpleNamespace(
        id_PK=id_usuario,
        nombre=nombre,
        correo_electronico=f"{nombre.lower()}@vitalia.com",
        rol_id_FK=rol_id,
        estado="activo",
    )


def entrar_como(rol_id, resultados=None, id_usuario=1):
    """Autentica como `rol_id` y devuelve la FakeDB inyectada en la API."""
    from app.models.role import Role

    res = {Role: SimpleNamespace(id_PK=rol_id, nombre=NOMBRE_ROL[rol_id], esta_activo=True)}
    res.update(resultados or {})
    db = FakeDB(res)
    app.dependency_overrides[get_current_user] = lambda: usuario(rol_id, id_usuario)
    app.dependency_overrides[get_db] = lambda: db
    return db


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()

from app.models.cita import Cita
from app.models.doctor import Doctor
from app.models.paciente import Paciente
from app.models.usuario import Usuario


# ------------------------------------------------------------------ USUARIOS
def datos_usuario(**extra):
    base = {
        "nombre": "Ana Recepción",
        "correo_electronico": "ana@vitalia.com",
        "password": "Segura1234",
        "rol_id_FK": RECEPCION,
    }
    base.update(extra)
    return base


def test_crear_usuario_recepcionista_exitoso():
    db = entrar_como(ADMIN, {Usuario: None})
    r = client.post("/api/usuarios/", json=datos_usuario())
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["correo_electronico"] == "ana@vitalia.com"
    assert cuerpo["rol_id_FK"] == RECEPCION
    assert cuerpo["estado"] == "activo"
    assert db.commits == 1
    # La contraseña nunca se guarda ni se devuelve en claro
    assert "password" not in cuerpo
    assert db.agregados[0].hash_contrasena != "Segura1234"


def test_crear_usuario_correo_invalido_422():
    entrar_como(ADMIN, {Usuario: None})
    r = client.post("/api/usuarios/", json=datos_usuario(correo_electronico="no-es-correo"))
    assert r.status_code == 422


def test_crear_usuario_sin_campos_obligatorios_422():
    entrar_como(ADMIN, {Usuario: None})
    r = client.post("/api/usuarios/", json={"nombre": "Solo nombre"})
    assert r.status_code == 422


def test_crear_usuario_correo_duplicado_400():
    entrar_como(ADMIN, {Usuario: usuario(RECEPCION, 9, "Existente")})
    r = client.post("/api/usuarios/", json=datos_usuario())
    assert r.status_code == 400
    assert "correo" in r.json()["detail"].lower()


def test_crear_paciente_sin_apellido_400():
    db = entrar_como(ADMIN, {Usuario: None})
    r = client.post("/api/usuarios/", json=datos_usuario(rol_id_FK=PACIENTE))
    assert r.status_code == 400
    assert "apellido" in r.json()["detail"].lower()
    assert db.rollbacks == 1  # no queda nada a medias en la base de datos


def test_crear_paciente_con_apellido_crea_perfil_paciente():
    db = entrar_como(ADMIN, {Usuario: None})
    r = client.post(
        "/api/usuarios/",
        json=datos_usuario(rol_id_FK=PACIENTE, apellido="Pérez", genero="F"),
    )
    assert r.status_code == 201, r.text
    assert any(isinstance(o, Paciente) and o.apellido == "Pérez" for o in db.agregados)


def test_paciente_no_puede_crear_usuarios_403():
    entrar_como(PACIENTE, {Usuario: None})
    assert client.post("/api/usuarios/", json=datos_usuario()).status_code == 403


# --------------------------------------------------------------------- SALAS
def test_crear_sala_valida():
    entrar_como(ADMIN)
    sala = SimpleNamespace(
        id_PK=1, nombre="Sala 1", tipo="consulta", ubicacion=None,
        estado="disponible", capacidad=4, piso="1", lista_equipamiento=None,
    )
    with patch("app.routers.salas.SalaService") as servicio:
        servicio.return_value.crear.return_value = sala
        r = client.post("/api/salas", json={"nombre": "Sala 1", "capacidad": 4})
    assert r.status_code == 201
    assert r.json()["nombre"] == "Sala 1"


@pytest.mark.parametrize("payload", [{}, {"nombre": "X", "capacidad": 0}, {"nombre": "X" * 151}])
def test_crear_sala_datos_invalidos_422(payload):
    entrar_como(ADMIN)
    assert client.post("/api/salas", json=payload).status_code == 422


def test_estado_sala_invalido_422():
    entrar_como(ADMIN)
    r = client.patch("/api/salas/1/estado", json={"estado": "volando"})
    assert r.status_code == 422


def test_editar_sala_inexistente_404():
    entrar_como(ADMIN)
    with patch("app.routers.salas.SalaService") as servicio:
        servicio.return_value.actualizar.return_value = None
        r = client.put("/api/salas/999", json={"nombre": "Nueva"})
    assert r.status_code == 404


def test_eliminar_sala_existente_204_e_inexistente_404():
    entrar_como(ADMIN)
    with patch("app.routers.salas.SalaService") as servicio:
        servicio.return_value.eliminar.return_value = True
        assert client.delete("/api/salas/1").status_code == 204
        servicio.return_value.eliminar.return_value = False
        assert client.delete("/api/salas/999").status_code == 404


# --------------------------------------------------------------------- CITAS
def cita_json(**extra):
    base = {
        "paciente_id_FK": 1, "doctor_id_FK": 1, "fecha": "2030-01-10",
        "hora_inicio": "09:00", "hora_fin": "09:30",
    }
    base.update(extra)
    return base


def test_crear_cita_campos_faltantes_422():
    entrar_como(RECEPCION)
    assert client.post("/api/citas/", json={"paciente_id_FK": 1}).status_code == 422


def test_crear_cita_paciente_inexistente_404():
    entrar_como(RECEPCION, {Paciente: None})
    r = client.post("/api/citas/", json=cita_json())
    assert r.status_code == 404


def test_crear_cita_hora_fin_anterior_a_inicio_422():
    pac = SimpleNamespace(id_PK=1, nombre="Luis", apellido="Gómez", usuario_id_FK=None, correo_electronico=None)
    doc = SimpleNamespace(id_PK=1, usuario_id_FK=2, nombre="Dr. Ruiz")
    entrar_como(RECEPCION, {Paciente: pac, Doctor: doc})
    with patch("app.routers.citas.has_valid_credentials", return_value=False):
        r = client.post("/api/citas/", json=cita_json(hora_inicio="10:00", hora_fin="09:00"))
    assert r.status_code == 422


def test_crear_cita_con_equipo_exige_sala_422():
    pac = SimpleNamespace(id_PK=1, nombre="Luis", apellido="Gómez", usuario_id_FK=None, correo_electronico=None)
    doc = SimpleNamespace(id_PK=1, usuario_id_FK=2, nombre="Dr. Ruiz")
    entrar_como(RECEPCION, {Paciente: pac, Doctor: doc})
    with patch("app.routers.citas.has_valid_credentials", return_value=False):
        r = client.post("/api/citas/", json=cita_json(requiere_equipo=True))
    assert r.status_code == 422


def test_cambiar_estado_cita_invalido_422():
    entrar_como(RECEPCION)
    r = client.patch("/api/citas/1/estado", json={"estado": "inventado"})
    assert r.status_code == 422


def test_cambiar_estado_cita_inexistente_404():
    entrar_como(RECEPCION, {Cita: None})
    r = client.patch("/api/citas/999/estado", json={"estado": "no_asistio"})
    assert r.status_code == 404


def test_marcar_no_asistio_se_guarda_y_se_refleja():
    cita = Cita(id_PK=5, paciente_id_FK=1, doctor_id_FK=1, fecha=date(2030, 1, 10),
                hora_inicio=time(9), hora_fin=time(9, 30), estado="programada")
    db = entrar_como(RECEPCION, {Cita: cita})
    r = client.patch("/api/citas/5/estado", json={"estado": "no_asistio"})
    assert r.status_code == 200, r.text
    assert cita.estado == "no_asistio"
    assert r.json()["estado"] == "no_asistio"
    assert r.json()["no_realizada"] is True   # lo que verá el paciente en su pantalla
    assert db.commits == 1


def test_eliminar_cita_inexistente_404():
    entrar_como(RECEPCION, {Cita: None})
    assert client.delete("/api/citas/999").status_code == 404


def test_paciente_no_puede_eliminar_citas_403():
    entrar_como(PACIENTE)
    assert client.delete("/api/citas/1").status_code == 403


# ---------------------------------------------- CONSISTENCIA CON LA INTERFAZ
def test_cita_vencida_sin_completar_se_muestra_como_no_realizada():
    vieja = Cita(estado="programada", fecha=date(2020, 1, 1), hora_fin=time(10))
    futura = Cita(estado="programada", fecha=date(2099, 1, 1), hora_fin=time(10))
    hecha = Cita(estado="completada", fecha=date(2020, 1, 1), hora_fin=time(10))
    assert vieja.no_realizada is True
    assert futura.no_realizada is False
    assert hecha.no_realizada is False
