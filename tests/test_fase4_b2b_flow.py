"""Pruebas unitarias para el flujo de conversion B2B: Pre-registro, Webhook con custom_id y activacion."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.main import app
from app.models.clinica import Clinica
from app.models.role import Role
from app.models.usuario import Usuario


@pytest.fixture
def sesion_db():
    """Configura una base de datos en memoria para pruebas aisladas con roles y planes sembrados."""
    motor = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(motor, "connect")
    def habilitar_fk_sqlite(conexion_dbapi, registro_conexion):
        cursor = conexion_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(motor)
    fabrica_sesiones = sessionmaker(bind=motor, autocommit=False, autoflush=False)
    sesion = fabrica_sesiones()

    roles = [
        Role(id_PK=1, nombre="Administrador", descripcion="Admin", esta_activo=True),
        Role(id_PK=2, nombre="Doctor", descripcion="Doctor", esta_activo=True),
        Role(id_PK=3, nombre="Paciente", descripcion="Paciente", esta_activo=True),
        Role(id_PK=4, nombre="Recepción", descripcion="Recepcion", esta_activo=True),
        Role(id_PK=5, nombre="Coordinador", descripcion="Coordinador", esta_activo=True),
    ]
    sesion.add_all(roles)
    sesion.commit()

    sembrar_planes_y_clinica_demo(sesion)

    def anular_get_db():
        try:
            yield sesion
        finally:
            pass

    app.dependency_overrides[get_db] = anular_get_db

    try:
        yield sesion
    finally:
        app.dependency_overrides.pop(get_db, None)
        sesion.close()
        Base.metadata.drop_all(motor)


@pytest.fixture
def cliente(sesion_db):
    """Provee un cliente de pruebas HTTP."""
    return TestClient(app)


def test_preregistro_crea_clinica_y_admin_inactivos(sesion_db: Session, cliente: TestClient):
    """Verifica que el pre-registro guarda temporalmente la clinica y administrador con estado inactivo."""
    payload_registro = {
        "nombre_clinica": "Clínica San Patricio",
        "nombre_admin": "Dr. Fernando Ruiz",
        "correo": "fernando.ruiz@sanpatricio.com",
        "password": "PasswordSegura123!",
        "paypal_plan_id": "P-5CC29855SK5899208NLWUMWI",
    }

    respuesta = cliente.post("/api/suscripciones/pre-registro", json=payload_registro)

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert "clinica_id" in datos
    clinica_id = datos["clinica_id"]

    clinica = sesion_db.query(Clinica).filter(Clinica.id_PK == clinica_id).first()
    assert clinica is not None
    assert clinica.activa is False
    assert clinica.nombre_comercial == "Clínica San Patricio"
    assert clinica.paypal_subscription_id is None

    admin = sesion_db.query(Usuario).filter(Usuario.correo_electronico == "fernando.ruiz@sanpatricio.com").first()
    assert admin is not None
    assert admin.clinica_id_FK == clinica.id_PK
    assert admin.estado == "inactivo"
    assert admin.rol_id_FK == 1


def test_webhook_paypal_activa_clinica_preregistrada_con_custom_id(sesion_db: Session, cliente: TestClient):
    """Verifica que el webhook extrae el custom_id, activa la clinica, su admin y dispara el correo de bienvenida."""
    payload_registro = {
        "nombre_clinica": "Hospital Metropolitano",
        "nombre_admin": "Dra. Elena Vasquez",
        "correo": "elena.vasquez@metro.com",
        "password": "PasswordMetro456!",
        "paypal_plan_id": "P-5J121652NS326140HNLWUNNI",
    }
    resp_registro = cliente.post("/api/suscripciones/pre-registro", json=payload_registro)
    assert resp_registro.status_code == 201
    clinica_id = resp_registro.json()["clinica_id"]

    payload_webhook = {
        "id": "WH-B2B-ACTIVATED-777",
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": "I-SUB-PAYPAL-B2B-123",
            "plan_id": "P-5J121652NS326140HNLWUNNI",
            "custom_id": str(clinica_id),
            "status": "ACTIVE",
            "subscriber": {
                "email_address": "elena.vasquez@metro.com",
                "name": {
                    "given_name": "Elena",
                    "surname": "Vasquez"
                }
            }
        }
    }

    with patch("app.services.provisioning_service.enviar_correo_bienvenida_admin") as mock_email:
        mock_email.return_value = True

        respuesta = cliente.post("/api/webhooks/paypal", json=payload_webhook)

        assert respuesta.status_code == 200
        datos_resp = respuesta.json()
        assert datos_resp["status"] == "success"
        assert datos_resp["clinica_id"] == clinica_id

        clinica = sesion_db.query(Clinica).filter(Clinica.id_PK == clinica_id).first()
        assert clinica is not None
        assert clinica.activa is True
        assert clinica.paypal_subscription_id == "I-SUB-PAYPAL-B2B-123"

        admin = sesion_db.query(Usuario).filter(Usuario.correo_electronico == "elena.vasquez@metro.com").first()
        assert admin is not None
        assert admin.estado == "activo"

        mock_email.assert_called_once()
        args, kwargs = mock_email.call_args
        assert kwargs.get("destinatario") == "elena.vasquez@metro.com" or args[0] == "elena.vasquez@metro.com"


def test_preregistro_plan_inexistente_retorna_404(sesion_db: Session, cliente: TestClient):
    """Verifica que intentar pre-registrar una clinica con un plan desconocido lance error 404."""
    payload_invalido = {
        "nombre_clinica": "Clínica Fantasma",
        "nombre_admin": "Admin Fantasma",
        "correo": "fantasma@vitalia.com",
        "password": "Password123!",
        "paypal_plan_id": "P-PLAN-INEXISTENTE-999",
    }

    respuesta = cliente.post("/api/suscripciones/pre-registro", json=payload_invalido)
    assert respuesta.status_code == 404
