"""Pruebas unitarias para la Fase 3: Aprovisionamiento de tenants y webhooks de PayPal."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verificar_password
from app.database.connection import Base, get_db
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.main import app
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.services.provisioning_service import aprovisionar_tenant_paypal


@pytest.fixture
def sesion_db():
    """Configura una base de datos SQLite en memoria con claves foraneas activadas y datos semilla."""
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
    """Provee un cliente de pruebas HTTP para ejecutar peticiones sobre la aplicacion FastAPI."""
    return TestClient(app)


def test_webhook_activacion_suscripcion_crea_clinica_y_admin(sesion_db: Session, cliente: TestClient):
    """Verifica que el webhook de activacion aprovisiona la clinica y crea el usuario administrador inicial."""
    payload_activacion = {
        "id": "WH-TEST-ACTIVATED-001",
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": "I-SUB-ACT-123456",
            "plan_id": "P-9JA53339DW996433FNLXJMJA",
            "status": "ACTIVE",
            "subscriber": {
                "email_address": "admin.dr@nuevaclinica.com",
                "name": {
                    "given_name": "Carlos",
                    "surname": "Mendoza"
                }
            },
            "custom_id": "Clínica Los Olivos"
        }
    }

    respuesta = cliente.post("/api/webhooks/paypal", json=payload_activacion)

    assert respuesta.status_code == 200
    datos_respuesta = respuesta.json()
    assert datos_respuesta["status"] == "success"
    assert datos_respuesta["event_type"] == "BILLING.SUBSCRIPTION.ACTIVATED"

    clinica_creada = sesion_db.query(Clinica).filter(
        Clinica.paypal_subscription_id == "I-SUB-ACT-123456"
    ).first()

    assert clinica_creada is not None
    assert clinica_creada.activa is True
    assert clinica_creada.nombre_comercial == "Clínica Los Olivos"
    assert clinica_creada.plan.nombre == "Básico"
    assert clinica_creada.plan.paypal_plan_id == "P-9JA53339DW996433FNLXJMJA"

    admin_creado = sesion_db.query(Usuario).filter(
        Usuario.correo_electronico == "admin.dr@nuevaclinica.com"
    ).first()

    assert admin_creado is not None
    assert admin_creado.clinica_id_FK == clinica_creada.id_PK
    assert admin_creado.nombre == "Carlos"
    assert admin_creado.apellido_paterno == "Mendoza"
    assert admin_creado.rol_id_FK == 1
    assert admin_creado.estado == "activo"
    assert len(admin_creado.hash_contrasena) > 20


def test_webhook_cancelacion_suscripcion_desactiva_clinica(sesion_db: Session, cliente: TestClient):
    """Verifica que el webhook de cancelacion cambia el estado de la clinica a inactiva revocando su acceso."""
    plan_clinica = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Clínica"
    ).first()

    clinica = Clinica(
        nombre_comercial="Clínica San Telmo",
        plan_id_FK=plan_clinica.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
        paypal_subscription_id="I-SUB-CAN-789012"
    )
    sesion_db.add(clinica)
    sesion_db.commit()

    payload_cancelacion = {
        "id": "WH-TEST-CANCELLED-002",
        "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
        "resource": {
            "id": "I-SUB-CAN-789012"
        }
    }

    respuesta = cliente.post("/api/webhooks/paypal", json=payload_cancelacion)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["status"] == "success"
    assert datos["activa"] is False

    sesion_db.refresh(clinica)
    assert clinica.activa is False


def test_webhook_pago_fallido_desactiva_clinica(sesion_db: Session, cliente: TestClient):
    """Verifica que el evento de fallo en pago recurrente revoca el acceso desactivando la clinica."""
    plan_pro = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Profesional"
    ).first()

    clinica = Clinica(
        nombre_comercial="Clínica Santa Clara",
        plan_id_FK=plan_pro.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
        paypal_subscription_id="I-SUB-FAIL-345678"
    )
    sesion_db.add(clinica)
    sesion_db.commit()

    payload_fallo = {
        "id": "WH-TEST-FAILED-003",
        "event_type": "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
        "resource": {
            "id": "I-SUB-FAIL-345678"
        }
    }

    respuesta = cliente.post("/api/webhooks/paypal", json=payload_fallo)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["status"] == "success"
    assert datos["activa"] is False

    sesion_db.refresh(clinica)
    assert clinica.activa is False


def test_webhook_plan_inexistente_retorna_404_y_mantiene_consistencia(
    sesion_db: Session, cliente: TestClient
):
    """Verifica que un plan de PayPal inexistente provoque un rollback y devuelva 404."""
    payload_invalido = {
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": "I-SUB-INVALID-999",
            "plan_id": "P-INEXISTENTE-99999",
            "subscriber": {
                "email_address": "error@vitalia.com",
                "name": {
                    "given_name": "Error"
                }
            }
        }
    }

    respuesta = cliente.post("/api/webhooks/paypal", json=payload_invalido)

    assert respuesta.status_code == 404

    clinica = sesion_db.query(Clinica).filter(
        Clinica.paypal_subscription_id == "I-SUB-INVALID-999"
    ).first()
    assert clinica is None


def test_servicio_aprovisionamiento_genera_password_temporal_valida(sesion_db: Session):
    """Verifica directamente el servicio de aprovisionamiento y que la contrasena temporal es autenticable."""
    payload = {
        "resource": {
            "id": "I-SUB-DIRECT-55555",
            "plan_id": "P-3BM73023B1884583RNLXJOSQ",
            "subscriber": {
                "email_address": "directo@empresarial.com",
                "name": {
                    "given_name": "Roberto",
                    "surname": "Sanchez"
                }
            },
            "custom_id": "Hospital Privado Directo"
        }
    }

    resultado = aprovisionar_tenant_paypal(sesion_db, payload)

    assert resultado.clinica.id_PK is not None
    assert resultado.clinica.nombre_comercial == "Hospital Privado Directo"
    assert resultado.usuario.correo_electronico == "directo@empresarial.com"
    assert len(resultado.password_temporal) >= 12
    assert verificar_password(resultado.password_temporal, resultado.usuario.hash_contrasena) is True
