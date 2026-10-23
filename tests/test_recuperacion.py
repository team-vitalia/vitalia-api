"""Pruebas de recuperación de contraseña (correo + QR) y listado enriquecido.
Usan SQLite en memoria; no requieren MySQL ni SMTP."""
import re
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import generar_hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.doctor import Doctor
from app.models.doctor_especialidad import DoctorEspecialidad
from app.models.especialidad import Especialidad
from app.models.role import Role
from app.models.usuario import Usuario
from app.services import recuperacion_service as rec

PASS = "Clave1234"


@pytest.fixture()
def entorno(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Sesion = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    db = Sesion()
    for i, n in enumerate(["Administrador", "Doctor", "Paciente", "Recepción", "Coordinador"], 1):
        db.add(Role(id_PK=i, nombre=n, esta_activo=True))

    def usuario(id_, nombre, correo, rol, estado="activo"):
        db.add(Usuario(id_PK=id_, nombre=nombre, correo_electronico=correo,
                       hash_contrasena=generar_hash_password(PASS), rol_id_FK=rol,
                       estado=estado, intentos_fallidos=0))

    usuario(1, "Admin", "admin@x.com", 1)
    usuario(2, "Dra Ana", "ana@x.com", 2)
    usuario(3, "Pablo", "pablo@x.com", 3)
    usuario(4, "Coord", "coord@x.com", 5)
    usuario(5, "Inactivo", "off@x.com", 4, estado="inactivo")
    db.add(Especialidad(id_PK=1, nombre="Cardiología", esta_activo=True))
    db.add(Especialidad(id_PK=2, nombre="Pediatría", esta_activo=True))
    db.commit()
    db.add(Doctor(id_PK=1, usuario_id_FK=2, numero_licencia="L1", estado="activo"))
    db.commit()
    db.add_all([DoctorEspecialidad(doctor_id_FK=1, especialidad_id_FK=1),
                DoctorEspecialidad(doctor_id_FK=1, especialidad_id_FK=2)])
    db.commit()
    db.close()

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    correos = MagicMock()
    monkeypatch.setattr("app.routers.recuperacion.enviar_correo_sincrono", correos)
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app), correos, Sesion
    app.dependency_overrides.pop(get_db, None)


def login(c, correo, password=PASS):
    return c.post("/api/auth/login", json={"correo_electronico": correo, "password": password})


def auth(c, correo):
    return {"Authorization": f"Bearer {login(c, correo).json()['access_token']}"}


def codigo_enviado(correos):
    return re.search(r"\b(\d{6})\b", correos.call_args.args[3]).group(1)


# ---------------- correo ----------------

def test_flujo_correo_completo(entorno):
    c, correos, _ = entorno
    r = c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    assert r.status_code == 200
    codigo = codigo_enviado(correos)

    malo = "000000" if codigo != "000000" else "111111"
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": malo, "nueva_password": "Nueva12345"})
    assert r.status_code == 400

    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": codigo, "nueva_password": "Nueva12345"})
    assert r.status_code == 200
    assert login(c, "ana@x.com", "Nueva12345").status_code == 200
    assert login(c, "ana@x.com", PASS).status_code != 200

    # el código es de un solo uso
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": codigo, "nueva_password": "Otra123456"})
    assert r.status_code == 400


def test_no_revela_si_el_correo_existe(entorno):
    c, correos, _ = entorno
    a = c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    b = c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "nadie@x.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert correos.call_count == 1  # solo se envió al existente


def test_usuario_inactivo_no_recibe_codigo(entorno):
    c, correos, _ = entorno
    c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "off@x.com"})
    assert correos.call_count == 0


def test_reenvio_limitado_a_uno_por_minuto(entorno):
    c, correos, _ = entorno
    for _ in range(3):
        c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    assert correos.call_count == 1


def test_cinco_intentos_fallidos_invalidan_el_codigo(entorno):
    c, correos, _ = entorno
    c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    bueno = codigo_enviado(correos)
    malo = "123456" if bueno != "123456" else "654321"
    for _ in range(5):
        c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": malo, "nueva_password": "Nueva12345"})
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": bueno, "nueva_password": "Nueva12345"})
    assert r.status_code == 400


def test_codigo_vencido(entorno, monkeypatch):
    c, correos, _ = entorno
    c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    codigo = codigo_enviado(correos)
    ahora = time.time()
    monkeypatch.setattr(rec.time, "time", lambda: ahora + 11 * 60)
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": codigo, "nueva_password": "Nueva12345"})
    assert r.status_code == 400


def test_password_corta_rechazada(entorno):
    c, _, _ = entorno
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "ana@x.com", "codigo": "123456", "nueva_password": "corta"})
    assert r.status_code == 422


def test_el_token_no_se_guarda_en_claro(entorno):
    c, correos, Sesion = entorno
    c.post("/api/auth/recuperar/correo/solicitar", json={"correo_electronico": "ana@x.com"})
    codigo = codigo_enviado(correos)
    guardado = Sesion().get(Usuario, 2).token_restablecimiento
    assert guardado and codigo not in guardado.split(":")[-1]


# ---------------- QR ----------------

def test_flujo_qr_completo(entorno):
    c, _, _ = entorno
    r = c.post("/api/auth/recuperar/qr/generar/3", headers=auth(c, "admin@x.com"))
    assert r.status_code == 200
    _, uid, token = r.json()["payload"].split(":")

    r = c.post("/api/auth/recuperar/qr/confirmar",
               json={"usuario_id": int(uid), "token": "x" * 43, "nueva_password": "Nueva12345"})
    assert r.status_code == 400

    r = c.post("/api/auth/recuperar/qr/confirmar",
               json={"usuario_id": int(uid), "token": token, "nueva_password": "Nueva12345"})
    assert r.status_code == 200
    assert login(c, "pablo@x.com", "Nueva12345").status_code == 200

    r = c.post("/api/auth/recuperar/qr/confirmar",
               json={"usuario_id": int(uid), "token": token, "nueva_password": "Otra123456"})
    assert r.status_code == 400


def test_qr_requiere_admin_o_coordinador(entorno):
    c, _, _ = entorno
    assert c.post("/api/auth/recuperar/qr/generar/2").status_code in (401, 403)
    assert c.post("/api/auth/recuperar/qr/generar/2", headers=auth(c, "pablo@x.com")).status_code == 403


def test_coordinador_no_genera_qr_para_admin(entorno):
    c, _, _ = entorno
    h = auth(c, "coord@x.com")
    assert c.post("/api/auth/recuperar/qr/generar/1", headers=h).status_code == 403
    assert c.post("/api/auth/recuperar/qr/generar/3", headers=h).status_code == 200


def test_qr_no_sirve_como_codigo_de_correo(entorno):
    c, _, _ = entorno
    c.post("/api/auth/recuperar/qr/generar/3", headers=auth(c, "admin@x.com"))
    r = c.post("/api/auth/recuperar/correo/confirmar",
               json={"correo_electronico": "pablo@x.com", "codigo": "123456", "nueva_password": "Nueva12345"})
    assert r.status_code == 400


def test_qr_para_cuenta_inactiva_rechazado(entorno):
    c, _, _ = entorno
    assert c.post("/api/auth/recuperar/qr/generar/5", headers=auth(c, "admin@x.com")).status_code == 409


# ---------------- listado enriquecido ----------------

def test_listado_incluye_especialidades_del_doctor(entorno):
    c, _, _ = entorno
    filas = c.get("/api/usuarios/", headers=auth(c, "admin@x.com")).json()
    ana = next(f for f in filas if f["id_PK"] == 2)
    assert ana["doctor_id"] == 1
    assert [e["nombre"] for e in ana["especialidades"]] == ["Cardiología", "Pediatría"]
    pablo = next(f for f in filas if f["id_PK"] == 3)
    assert pablo["especialidades"] == [] and pablo["doctor_id"] is None
