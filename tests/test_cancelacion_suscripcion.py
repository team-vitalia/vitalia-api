from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import crear_access_token, generar_hash_password
from app.core.dependencies import get_current_user
from app.main import app
from app.models.cancelacion_suscripcion import CancelacionSuscripcion
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario


@pytest.fixture
def cliente(sesion_db):
    return TestClient(app)


def test_cancelacion_dia_5_con_reembolso_downgrade_gratuito(sesion_db: Session, cliente: TestClient):
    plan_basico = sesion_db.query(PlanSuscripcion).filter(PlanSuscripcion.nombre == "Básico").first()

    clinica = Clinica(
        nombre_comercial="Clinica Dia Cinco",
        plan_id_FK=plan_basico.id_PK,
        activa=True,
        fecha_registro=datetime.now() - timedelta(days=5),
        fecha_inicio_suscripcion=datetime.now() - timedelta(days=5),
        paypal_subscription_id="I-SUB-DIA-5",
        ultimo_pago_capture_id="CAP-PAGO-005",
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    admin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin Cinco",
        correo_electronico="admin.cinco@clinica.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin)
    sesion_db.commit()

    token = crear_access_token({"sub": str(admin.id_PK), "rol_id": 1, "clinica_id": clinica.id_PK})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "motivo_categoria": "PRECIO_ALTO",
        "comentarios_adicionales": "Precio elevado para mi volumen de pacientes",
        "solicitar_reembolso": True,
    }

    with patch("app.routers.suscripciones.cancelar_suscripcion_paypal", return_value=True) as mock_cancel, \
         patch("app.routers.suscripciones.reembolsar_captura_paypal", return_value="REFUND-PAYPAL-005") as mock_refund:
        respuesta = cliente.post("/api/suscripciones/cancelar", json=payload, headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["status"] == "success"
    assert datos["aplica_reembolso"] is True
    assert datos["estado_reembolso"] == "PROCESADO"
    assert datos["paypal_refund_id"] == "REFUND-PAYPAL-005"
    assert datos["plan_actual"] == "Gratuito"

    sesion_db.refresh(clinica)
    assert clinica.plan.nombre == "Gratuito"
    assert clinica.paypal_subscription_id is None
    assert clinica.activa is True

    cancelacion = sesion_db.query(CancelacionSuscripcion).filter(
        CancelacionSuscripcion.clinica_id_FK == clinica.id_PK
    ).first()
    assert cancelacion is not None
    assert cancelacion.plan_anterior_id_FK == plan_basico.id_PK
    assert cancelacion.motivo_categoria == "PRECIO_ALTO"
    assert cancelacion.aplica_reembolso is True
    assert cancelacion.estado_reembolso == "PROCESADO"
    assert cancelacion.paypal_refund_id == "REFUND-PAYPAL-005"


def test_cancelacion_dia_15_sin_reembolso_downgrade_gratuito(sesion_db: Session, cliente: TestClient):
    plan_clinica = sesion_db.query(PlanSuscripcion).filter(PlanSuscripcion.nombre == "Clínica").first()

    clinica = Clinica(
        nombre_comercial="Clinica Dia Quince",
        plan_id_FK=plan_clinica.id_PK,
        activa=True,
        fecha_registro=datetime.now() - timedelta(days=15),
        fecha_inicio_suscripcion=datetime.now() - timedelta(days=15),
        paypal_subscription_id="I-SUB-DIA-15",
        ultimo_pago_capture_id="CAP-PAGO-015",
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    admin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin Quince",
        correo_electronico="admin.quince@clinica.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin)
    sesion_db.commit()

    token = crear_access_token({"sub": str(admin.id_PK), "rol_id": 1, "clinica_id": clinica.id_PK})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "motivo_categoria": "FALTA_FUNCIONES",
        "comentarios_adicionales": "Requiero funciones no disponibles",
        "solicitar_reembolso": True,
    }

    with patch("app.routers.suscripciones.cancelar_suscripcion_paypal", return_value=True) as mock_cancel, \
         patch("app.routers.suscripciones.reembolsar_captura_paypal") as mock_refund:
        respuesta = cliente.post("/api/suscripciones/cancelar", json=payload, headers=headers)
        mock_refund.assert_not_called()

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["status"] == "success"
    assert datos["aplica_reembolso"] is False
    assert datos["estado_reembolso"] == "NO_APLICA"
    assert datos["paypal_refund_id"] is None
    assert datos["plan_actual"] == "Gratuito"

    sesion_db.refresh(clinica)
    assert clinica.plan.nombre == "Gratuito"
    assert clinica.paypal_subscription_id is None
    assert clinica.activa is True

    cancelacion = sesion_db.query(CancelacionSuscripcion).filter(
        CancelacionSuscripcion.clinica_id_FK == clinica.id_PK
    ).first()
    assert cancelacion is not None
    assert cancelacion.plan_anterior_id_FK == plan_clinica.id_PK
    assert cancelacion.motivo_categoria == "FALTA_FUNCIONES"
    assert cancelacion.aplica_reembolso is False
    assert cancelacion.estado_reembolso == "NO_APLICA"
    assert cancelacion.paypal_refund_id is None


def test_superadmin_listar_cancelaciones_y_metricas(sesion_db: Session, cliente: TestClient):
    clinica = Clinica(
        nombre_comercial="Clinica Superadmin Demo",
        plan_id_FK=1,
        activa=True,
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Super Admin Cancelaciones",
        correo_electronico="superadmin.cancelaciones@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)

    plan_prof = sesion_db.query(PlanSuscripcion).filter(PlanSuscripcion.nombre == "Profesional").first()
    cancelacion_demo = CancelacionSuscripcion(
        clinica_id_FK=clinica.id_PK,
        plan_anterior_id_FK=plan_prof.id_PK,
        fecha_cancelacion=datetime.now(),
        motivo_categoria="CAMBIO_PROVEEDOR",
        comentarios_adicionales="Migracion a otro sistema",
        aplica_reembolso=True,
        estado_reembolso="PROCESADO",
        paypal_refund_id="REFUND-DEMO-001",
    )
    sesion_db.add(cancelacion_demo)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.get("/api/superadmin/cancelaciones")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert "total_cancelaciones" in datos
        assert datos["total_cancelaciones"] >= 1
        assert "total_reembolsos_procesados" in datos
        assert datos["total_reembolsos_procesados"] >= 1
        assert "motivos_conteo" in datos
        assert "CAMBIO_PROVEEDOR" in datos["motivos_conteo"]
        assert "estados_reembolso_conteo" in datos
        assert "PROCESADO" in datos["estados_reembolso_conteo"]
        assert "cancelaciones" in datos
        assert isinstance(datos["cancelaciones"], list)
        assert len(datos["cancelaciones"]) >= 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
