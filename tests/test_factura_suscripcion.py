from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.main import app
from app.models.clinica import Clinica
from app.models.role import Role
from app.models.usuario import Usuario
from app.services.invoice_service import generar_pdf_factura
from app.services.email_service import (
    generar_html_confirmacion_pago,
    enviar_correo_confirmacion_pago,
)


@pytest.fixture
def sesion_db():
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

    yield sesion

    app.dependency_overrides.clear()
    sesion.close()


def test_generar_pdf_factura():
    pdf = generar_pdf_factura(
        folio="F-2026-TEST01",
        fecha="11/11/2026 16:30",
        nombre_clinica="Clínica Santa María",
        nombre_admin="Dr. Jared",
        correo="test@vitalia.software",
        nombre_plan="Clínica",
        precio_mensual=1199.0,
        subscription_id="I-BW99999",
        es_upgrade=False,
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000
    assert pdf.startswith(b"%PDF")


def test_plantillas_html_bienvenida_y_upgrade():
    html_bienvenida = generar_html_confirmacion_pago(
        nombre_admin="Dr. Jared",
        nombre_clinica="Clínica Santa María",
        nombre_plan="Clínica",
        precio_mensual=1199.0,
        subscription_id="I-BW99999",
        es_upgrade=False,
    )
    assert "Bienvenido" in html_bienvenida
    assert "Clínica Santa María" in html_bienvenida
    assert "Plan Clínica" in html_bienvenida
    assert "Factura" in html_bienvenida

    html_upgrade = generar_html_confirmacion_pago(
        nombre_admin="Dr. Jared",
        nombre_clinica="Clínica Santa María",
        nombre_plan="Empresarial",
        precio_mensual=4499.0,
        subscription_id="I-BW88888",
        es_upgrade=True,
    )
    assert "activado correctamente" in html_upgrade
    assert "Bienvenido" not in html_upgrade
    assert "Empresarial" in html_upgrade
    assert "Factura" in html_upgrade


@patch("resend.Emails.send")
@patch.dict("os.environ", {"RESEND_API_KEY": "re_mock_test_key"})
def test_enviar_correo_confirmacion_bienvenida(mock_resend_send):
    mock_resend_send.return_value = {"id": "email_123"}

    exito = enviar_correo_confirmacion_pago(
        destinatario="admin@clinica.com",
        nombre_admin="Dra. Ana",
        nombre_clinica="Clínica Salud",
        nombre_plan="Profesional",
        precio_mensual=2199.0,
        subscription_id="I-BW12345",
        es_upgrade=False,
    )

    assert exito is True
    assert mock_resend_send.called
    llamada = mock_resend_send.call_args[0][0]
    assert llamada["subject"] == "¡Gracias por su compra!"
    assert llamada["to"] == ["admin@clinica.com"]
    assert "attachments" in llamada
    assert len(llamada["attachments"]) == 1
    assert llamada["attachments"][0]["filename"].startswith("Factura_Vitalia_")
    assert isinstance(llamada["attachments"][0]["content"], list)


@patch("resend.Emails.send")
@patch.dict("os.environ", {"RESEND_API_KEY": "re_mock_test_key"})
def test_enviar_correo_confirmacion_upgrade(mock_resend_send):
    mock_resend_send.return_value = {"id": "email_456"}

    exito = enviar_correo_confirmacion_pago(
        destinatario="admin@clinica.com",
        nombre_admin="Dra. Ana",
        nombre_clinica="Clínica Salud",
        nombre_plan="Empresarial",
        precio_mensual=4499.0,
        subscription_id="I-BW67890",
        es_upgrade=True,
    )

    assert exito is True
    assert mock_resend_send.called
    llamada = mock_resend_send.call_args[0][0]
    assert llamada["subject"] == "¡Gracias por su compra!"
    assert "activado correctamente" in llamada["html"]


def test_endpoint_confirmar_suscripcion_dispara_correo(sesion_db):
    client = TestClient(app)

    with patch("app.services.email_service.enviar_correo_confirmacion_pago") as mock_envio:
        mock_envio.return_value = True

        payload = {
            "subscription_id": "I-BW-PRUEBA-99",
            "paypal_plan_id": "P-18S21614P2665104JNLXJNKI",
            "correo": "contacto@nuevaclinica.com",
            "nombre_clinica": "Nueva Clínica San José",
            "nombre_admin": "Dra. Sofía",
            "modo": "registro",
            "es_upgrade": False,
        }

        res = client.post("/api/suscripciones/confirmar", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["activa"] is True
