"""
PRUEBA 4 - Acciones del rol COORDINADOR y datos estadísticos.

Comprueba qué puede y qué NO puede hacer el coordinador en usuarios, salas,
equipos, asignación de salas a doctores, reportes y auditoría.

Ejecutar:  pytest tests/test_coordinador_acciones.py -v

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

from app.models.doctor import Doctor
from app.models.usuario import Usuario

SALA = SimpleNamespace(id_PK=1, nombre="Sala 1", tipo="consulta", ubicacion=None,
                       estado="disponible", capacidad=4, piso="1", lista_equipamiento=None)


def nuevo_usuario(rol):
    return {"nombre": "Nuevo", "correo_electronico": f"n{rol}@vitalia.com",
            "password": "Segura1234", "rol_id_FK": rol}


# ------------------------------------------------------------ USUARIOS
@pytest.mark.parametrize("rol", [RECEPCION, DOCTOR])
def test_coordinador_puede_crear_personal_operativo(rol):
    entrar_como(COORDINADOR, {Usuario: None})
    r = client.post("/api/usuarios/", json=nuevo_usuario(rol))
    assert r.status_code == 201, r.text
    assert r.json()["rol_id_FK"] == rol


def test_coordinador_puede_crear_paciente_con_apellido():
    entrar_como(COORDINADOR, {Usuario: None})
    datos = nuevo_usuario(PACIENTE)
    datos["apellido"] = "López"
    assert client.post("/api/usuarios/", json=datos).status_code == 201


@pytest.mark.parametrize("rol", [ADMIN, COORDINADOR])
def test_coordinador_no_crea_administradores_ni_coordinadores(rol):
    db = entrar_como(COORDINADOR, {Usuario: None})
    r = client.post("/api/usuarios/", json=nuevo_usuario(rol))
    assert r.status_code == 403
    assert db.commits == 0


def test_administrador_si_puede_crear_coordinador():
    entrar_como(ADMIN, {Usuario: None})
    r = client.post("/api/usuarios/", json=nuevo_usuario(COORDINADOR))
    assert r.status_code == 201, r.text
    assert r.json()["rol_id_FK"] == COORDINADOR


def test_coordinador_puede_listar_usuarios():
    entrar_como(COORDINADOR, {Usuario: []})
    assert client.get("/api/usuarios/").status_code == 200


def test_coordinador_no_edita_cuentas_de_administrador():
    admin_objetivo = usuario(ADMIN, 1, "Admin")
    entrar_como(COORDINADOR, {Usuario: admin_objetivo}, id_usuario=5)
    r = client.patch("/api/usuarios/1", json={"nombre": "Hackeado"})
    assert r.status_code == 403


# --------------------------------------------------- SALAS Y EQUIPAMIENTO
def test_coordinador_crea_y_edita_salas():
    entrar_como(COORDINADOR)
    with patch("app.routers.salas.SalaService") as srv:
        srv.return_value.crear.return_value = SALA
        srv.return_value.actualizar.return_value = SALA
        assert client.post("/api/salas", json={"nombre": "Sala 1"}).status_code == 201
        assert client.put("/api/salas/1", json={"nombre": "Sala 1"}).status_code == 200


def test_coordinador_no_elimina_salas_ni_equipos_403():
    entrar_como(COORDINADOR)
    assert client.delete("/api/salas/1").status_code == 403
    assert client.delete("/api/equipamiento/1").status_code == 403


# -------------------------------------- ASIGNACIÓN DE SALAS A DOCTORES
def asignacion(**extra):
    base = {"sala_id_FK": 1, "dia_semana": 0, "hora_inicio": "08:00", "hora_fin": "12:00"}
    base.update(extra)
    return base


def test_coordinador_asigna_salas_a_un_doctor():
    from app.models.sala import Sala

    doc = SimpleNamespace(id_PK=1)
    db = entrar_como(COORDINADOR, {Doctor: doc, Sala: [(1,)]})
    r = client.put("/api/doctor-salas/doctor/1", json={"asignaciones": [asignacion()]})
    assert r.status_code == 200, r.text
    assert db.commits == 1


def test_asignacion_con_horas_invertidas_422():
    entrar_como(COORDINADOR)
    r = client.put("/api/doctor-salas/doctor/1",
                   json={"asignaciones": [asignacion(hora_inicio="12:00", hora_fin="08:00")]})
    assert r.status_code == 422


def test_asignacion_con_dia_invalido_422():
    entrar_como(COORDINADOR)
    r = client.put("/api/doctor-salas/doctor/1", json={"asignaciones": [asignacion(dia_semana=9)]})
    assert r.status_code == 422


def test_asignacion_con_horarios_traslapados_409():
    from app.models.sala import Sala

    entrar_como(COORDINADOR, {Doctor: SimpleNamespace(id_PK=1), Sala: [(1,)]})
    r = client.put("/api/doctor-salas/doctor/1", json={"asignaciones": [
        asignacion(hora_inicio="08:00", hora_fin="12:00"),
        asignacion(hora_inicio="11:00", hora_fin="13:00"),
    ]})
    assert r.status_code == 409


def test_asignar_a_doctor_inexistente_404():
    entrar_como(COORDINADOR, {Doctor: None})
    r = client.put("/api/doctor-salas/doctor/99", json={"asignaciones": [asignacion()]})
    assert r.status_code == 404


@pytest.mark.parametrize("rol", [DOCTOR, RECEPCION, PACIENTE])
def test_solo_admin_o_coordinador_asignan_salas_403(rol):
    entrar_como(rol)
    r = client.put("/api/doctor-salas/doctor/1", json={"asignaciones": [asignacion()]})
    assert r.status_code == 403


def test_doctor_consulta_solo_sus_salas_y_otros_roles_no():
    entrar_como(DOCTOR, {Doctor: None})
    assert client.get("/api/doctor-salas/mis-salas").status_code == 404   # sin perfil de doctor
    entrar_como(PACIENTE)
    assert client.get("/api/doctor-salas/mis-salas").status_code == 403


def test_validacion_de_horario_de_sala_para_citas():
    from app.routers.doctor_salas import sala_valida_para_cita

    lunes = date(2030, 1, 7)   # lunes
    db = FakeDB({})
    from app.models.doctor_sala import DoctorSala

    db.resultados[DoctorSala] = [SimpleNamespace(dia_semana=0, hora_inicio=time(8), hora_fin=time(12))]
    assert sala_valida_para_cita(db, 1, 1, lunes, time(9), time(10)) is True
    assert sala_valida_para_cita(db, 1, 1, lunes, time(11), time(13)) is False       # se pasa del horario
    assert sala_valida_para_cita(db, 1, 1, date(2030, 1, 8), time(9), time(10)) is False  # martes


# ------------------------------------------------------ REPORTES Y AUDITORÍA
def test_coordinador_consulta_todos_los_reportes_con_datos_correctos():
    entrar_como(COORDINADOR)
    with patch("app.routers.reportes.ReporteService") as srv:
        s = srv.return_value
        s.ocupacion_salas.return_value = {"total_salas": 2, "detalle": []}
        s.citas_por_doctor.return_value = {"total_citas": 9, "detalle": []}
        s.tiempos_espera.return_value = {"promedio_minutos": 12.5, "detalle": []}
        s.inventario_bajo.return_value = {"total": 1, "detalle": []}
        s.recetas.return_value = {"total": 4, "detalle": []}
        esperado = {
            "ocupacion-salas": ("total_salas", 2),
            "citas-por-doctor": ("total_citas", 9),
            "tiempos-espera": ("promedio_minutos", 12.5),
            "inventario-bajo": ("total", 1),
            "recetas": ("total", 4),
        }
        for ruta, (campo, valor) in esperado.items():
            r = client.get(f"/api/reportes/{ruta}")
            assert r.status_code == 200, ruta
            assert r.json()[campo] == valor, ruta


def test_coordinador_descarga_reportes_pdf_y_excel():
    entrar_como(COORDINADOR)
    with patch("app.routers.reportes.ReporteService") as srv:
        srv.return_value.recetas.return_value = {
            "desde": None, "hasta": None, "total": 3, "por_estado": {"emitida": 3},
            "detalle": [{"doctor_id": 1, "doctor": "Dra. Ana", "total": 3}]}
        assert client.get("/api/reportes/recetas/exportar?formato=pdf").content.startswith(b"%PDF")
        assert client.get("/api/reportes/recetas/exportar?formato=excel").content[:2] == b"PK"


def test_coordinador_consulta_auditoria():
    entrar_como(COORDINADOR)
    with patch("app.routers.auditoria.AuditoriaService") as srv:
        srv.return_value.listar.return_value = ([], 0)
        r = client.get("/api/auditoria")
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 0


def test_coordinador_puede_gestionar_citas_y_marcar_no_asistio():
    from app.models.cita import Cita

    cita = Cita(id_PK=1, fecha=date(2030, 1, 1), hora_inicio=time(9), hora_fin=time(10),
                estado="programada", doctor_id_FK=1, paciente_id_FK=1, requiere_equipo=False)
    entrar_como(COORDINADOR, {Cita: cita})
    r = client.patch("/api/citas/1/estado", json={"estado": "no_asistio"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "no_asistio"
