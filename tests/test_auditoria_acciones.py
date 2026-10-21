"""
PRUEBA 3 - Registro (auditoría) de las acciones realizadas por cada usuario.

Verifica que cada alta/edición/baja registre quién, qué, cuándo, desde dónde y
con qué valores; y que solo administración y coordinación puedan consultarlos.

Ejecutar:  pytest tests/test_auditoria_acciones.py -v

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

from app.models.registro_auditoria import RegistroAuditoria
from app.schemas.sala import SalaCreate, SalaUpdate
from app.services.sala_service import SalaService
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar


def _registros(db):
    return [o for o in db.agregados if isinstance(o, RegistroAuditoria)]


# ------------------------------------------------------ UTILIDADES
def test_registrar_auditoria_guarda_quien_que_cuando_y_valores():
    db = FakeDB()
    antes = datetime.now()
    registrar_auditoria(
        db=db, usuario=usuario(ADMIN, 7), accion="UPDATE", tabla="salas", id_registro=3,
        antiguos={"estado": "disponible"}, nuevos={"estado": "mantenimiento"},
        ip="10.0.0.5", descripcion="Cambio de estado",
    )
    reg = _registros(db)[0]
    assert reg.usuario_id_FK == 7
    assert reg.accion == "UPDATE"
    assert reg.nombre_tabla == "salas"
    assert reg.id_registro == 3
    assert reg.valores_antiguos == {"estado": "disponible"}
    assert reg.valores_nuevos == {"estado": "mantenimiento"}
    assert reg.direccion_ip == "10.0.0.5"
    assert reg.marca_tiempo >= antes


def test_auditoria_sin_usuario_no_falla():
    db = FakeDB()
    registrar_auditoria(db, None, "CREATE", "salas", 1, None, {"a": 1})
    assert _registros(db)[0].usuario_id_FK is None


def test_serializar_convierte_fechas_a_texto():
    r = serializar({"f": date(2030, 1, 2), "h": datetime(2030, 1, 2, 3, 4), "n": 5})
    assert r == {"f": "2030-01-02", "h": "2030-01-02T03:04:00", "n": 5}


def test_ip_toma_cabecera_forwarded_o_cliente():
    req = SimpleNamespace(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}, client=None)
    assert ip_desde_request(req) == "1.2.3.4"
    req2 = SimpleNamespace(headers={}, client=SimpleNamespace(host="9.9.9.9"))
    assert ip_desde_request(req2) == "9.9.9.9"
    assert ip_desde_request(None) is None


# ----------------------------------- LAS ACCIONES DE NEGOCIO QUEDAN REGISTRADAS
def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))


def test_crear_sala_registra_auditoria_create():
    db = FakeDB()
    SalaService(db).crear(SalaCreate(nombre="Sala A", capacidad=3), usuario(COORDINADOR, 5), _request())
    reg = _registros(db)[0]
    assert (reg.accion, reg.nombre_tabla) == ("CREATE", "salas")
    assert reg.usuario_id_FK == 5
    assert reg.valores_nuevos["nombre"] == "Sala A"
    assert reg.direccion_ip == "127.0.0.1"
    assert db.commits == 1


def test_editar_sala_registra_valores_antiguos_y_nuevos():
    from app.models.sala import Sala

    sala = Sala(id_PK=2, nombre="Vieja", estado="disponible")
    db = FakeDB({Sala: sala})
    db.scalar = lambda *a, **k: sala
    with patch.object(SalaService, "obtener", return_value=sala):
        SalaService(db).actualizar(2, SalaUpdate(nombre="Nueva"), usuario(ADMIN, 1), _request())
    regs = _registros(db)
    assert regs and regs[0].accion == "UPDATE"
    assert regs[0].valores_antiguos["nombre"] == "Vieja"
    assert regs[0].valores_nuevos["nombre"] == "Nueva"


# --------------------------------------------------------- CONSULTA DEL REGISTRO
def _fila_auditoria():
    return SimpleNamespace(
        id_PK=1, usuario_id_FK=5, accion="CREATE", id_registro=2, descripcion="Creación de sala",
        marca_tiempo=datetime(2030, 1, 1, 10, 0), nombre_tabla="salas",
        valores_antiguos=None, valores_nuevos={"nombre": "Sala A"}, direccion_ip="127.0.0.1",
    )


@pytest.mark.parametrize("rol", [ADMIN, COORDINADOR])
def test_admin_y_coordinador_consultan_auditoria(rol):
    entrar_como(rol)
    with patch("app.routers.auditoria.AuditoriaService") as srv:
        srv.return_value.listar.return_value = ([_fila_auditoria()], 1)
        r = client.get("/api/auditoria?nombre_tabla=salas&accion=CREATE")
        srv.return_value.listar.assert_called_once()
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["meta"]["total"] == 1
    assert cuerpo["data"][0]["usuario_id_FK"] == 5
    assert cuerpo["data"][0]["valores_nuevos"] == {"nombre": "Sala A"}


@pytest.mark.parametrize("rol", [DOCTOR, PACIENTE, RECEPCION])
def test_otros_roles_no_ven_auditoria_403(rol):
    entrar_como(rol)
    assert client.get("/api/auditoria").status_code == 403
    assert client.get("/api/auditoria/1").status_code == 403


def test_auditoria_sin_token_401():
    assert client.get("/api/auditoria").status_code == 401


def test_registro_de_auditoria_inexistente_404():
    entrar_como(ADMIN)
    with patch("app.routers.auditoria.AuditoriaService") as srv:
        srv.return_value.obtener.return_value = None
        assert client.get("/api/auditoria/999").status_code == 404


def test_paginacion_de_auditoria_fuera_de_rango_422():
    entrar_como(ADMIN)
    assert client.get("/api/auditoria?page=0").status_code == 422
    assert client.get("/api/auditoria?page_size=1000").status_code == 422
