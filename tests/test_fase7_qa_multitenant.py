"""Suite de pruebas unitarias y de integracion para la Fase 7: Aislamiento Multi-tenant, Limites de Plan y Mocking."""

from datetime import datetime
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generar_hash_password
from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.usuario import Usuario


def test_listado_usuarios_aislamiento_por_tenant(
    client: TestClient,
    setup_tenants: dict,
    db_session: Session,
):
    """Verifica que el Admin de Clinica A solo recibe usuarios de su propio clinica_id y no los de Clinica B."""
    clinica_a = setup_tenants["clinica_a"]
    clinica_b = setup_tenants["clinica_b"]
    headers_a = setup_tenants["headers_admin_a"]

    hash_pw = generar_hash_password("PasswordSegura123!")

    doc_a = Usuario(
        clinica_id_FK=clinica_a.id_PK,
        nombre="Doctor",
        apellido_paterno="Sanitas",
        correo_electronico="doctor.a@sanitas.com",
        hash_contrasena=hash_pw,
        rol_id_FK=2,
        estado="activo",
    )
    doc_b = Usuario(
        clinica_id_FK=clinica_b.id_PK,
        nombre="Doctor",
        apellido_paterno="Medica",
        correo_electronico="doctor.b@medica.com",
        hash_contrasena=hash_pw,
        rol_id_FK=2,
        estado="activo",
    )
    db_session.add_all([doc_a, doc_b])
    db_session.commit()

    respuesta = client.get("/api/usuarios/", headers=headers_a)
    assert respuesta.status_code == 200

    usuarios_obtenidos = respuesta.json()
    assert len(usuarios_obtenidos) >= 1

    correos = [u["correo_electronico"] for u in usuarios_obtenidos]
    assert "admin.a@sanitas.com" in correos
    assert "doctor.a@sanitas.com" in correos

    assert "admin.b@medica.com" not in correos
    assert "doctor.b@medica.com" not in correos


def test_bloqueo_edicion_usuario_otro_tenant(
    client: TestClient,
    setup_tenants: dict,
    db_session: Session,
):
    """Verifica que el Admin de Clinica A recibe 404 al intentar modificar un usuario perteneciente a Clinica B."""
    admin_b = setup_tenants["admin_b"]
    headers_a = setup_tenants["headers_admin_a"]
    nombre_original = admin_b.nombre

    payload_modificacion = {
        "nombre": "NombreMalicioso"
    }

    respuesta = client.patch(
        f"/api/usuarios/{admin_b.id_PK}",
        json=payload_modificacion,
        headers=headers_a,
    )
    assert respuesta.status_code in [403, 404]

    db_session.refresh(admin_b)
    assert admin_b.nombre == nombre_original


def test_forzado_clinica_id_creacion_paciente(
    client: TestClient,
    headers_admin_a: dict,
    clinica_a: Clinica,
    clinica_b: Clinica,
    db_session: Session,
):
    """Verifica que al registrar un paciente se asigna de forma forzosa el clinica_id del token emisor."""
    payload_paciente = {
        "nombre": "Carlos",
        "apellido": "Perez",
        "apellido_paterno": "Perez",
        "apellido_materno": "Lopez",
        "curp": "PELC900101HDFRZZ01",
        "fecha_nacimiento": "1990-01-01",
        "genero": "masculino",
        "telefono": "5551234567",
        "direccion": "Av. Principal 123",
        "correo_electronico": "carlos.perez.qa@test.com",
        "clinica_id_FK": clinica_b.id_PK,
        "clinica_id": clinica_b.id_PK,
    }

    respuesta = client.post(
        "/api/pacientes/",
        json=payload_paciente,
        headers=headers_admin_a,
    )
    assert respuesta.status_code == 201

    datos_paciente = respuesta.json()
    paciente_creado = db_session.query(Paciente).filter(
        Paciente.id_PK == datos_paciente["id_PK"]
    ).first()

    assert paciente_creado is not None
    assert paciente_creado.clinica_id_FK == clinica_a.id_PK
    assert paciente_creado.clinica_id_FK != clinica_b.id_PK


def test_bloqueo_limite_personal_plan_basico(
    client: TestClient,
    headers_admin_a: dict,
    clinica_a: Clinica,
    db_session: Session,
):
    """Verifica que la Clinica A (plan Basico, limite de 3 cuentas) arroja 403 Forbidden al intentar crear el 4to usuario."""
    hash_pw = generar_hash_password("PasswordSegura123!")

    personal_2 = Usuario(
        clinica_id_FK=clinica_a.id_PK,
        nombre="Recepcionista",
        apellido_paterno="Sanitas",
        correo_electronico="recep.sanitas@clinica-a.com",
        hash_contrasena=hash_pw,
        rol_id_FK=4,
        estado="activo",
    )
    personal_3 = Usuario(
        clinica_id_FK=clinica_a.id_PK,
        nombre="Doctor",
        apellido_paterno="Sanitas",
        correo_electronico="doc.sanitas@clinica-a.com",
        hash_contrasena=hash_pw,
        rol_id_FK=2,
        estado="activo",
    )
    db_session.add_all([personal_2, personal_3])
    db_session.commit()

    total_actual = db_session.query(Usuario).filter(Usuario.clinica_id_FK == clinica_a.id_PK).count()
    assert total_actual == 3

    payload_cuarto_usuario = {
        "nombre": "Enfermero",
        "apellido_paterno": "Cuatro",
        "apellido_materno": "Sanitas",
        "correo_electronico": "enfermero4@clinica-a.com",
        "password": "PasswordValido123!",
        "rol_id_FK": 4,
    }

    respuesta = client.post(
        "/api/usuarios/",
        json=payload_cuarto_usuario,
        headers=headers_admin_a,
    )
    assert respuesta.status_code == 403
    assert "Límite de personal alcanzado" in respuesta.json()["detail"]


def test_restriccion_modulo_contratos_por_plan(
    client: TestClient,
    headers_admin_a: dict,
    headers_admin_b: dict,
):
    """Verifica que Clinica A (plan Basico) recibe 403 al acceder a contratos, mientras Clinica B (plan Empresarial) recibe 200."""
    respuesta_a = client.get("/api/contratos/", headers=headers_admin_a)
    assert respuesta_a.status_code == 403
    assert "Gestión de Contratos" in respuesta_a.json()["detail"]

    respuesta_b = client.get("/api/contratos/", headers=headers_admin_b)
    assert respuesta_b.status_code == 200
    assert isinstance(respuesta_b.json(), list)


def test_mocking_validacion_webhook_paypal_y_activacion_tenant(
    client: TestClient,
    db_session: Session,
):
    """Verifica con unittest.mock.patch que el webhook de PayPal activa la clinica y administrador sin peticiones HTTP externas."""
    clinica_inactiva = Clinica(
        id_PK=99,
        nombre_comercial="Clínica Pendiente Activación",
        plan_id_FK=2,
        activa=False,
        fecha_registro=datetime.now(),
        paypal_subscription_id=None,
    )
    admin_inactivo = Usuario(
        id_PK=99,
        clinica_id_FK=99,
        nombre="Admin",
        apellido_paterno="Pendiente",
        correo_electronico="admin.pendiente@vitalia-qa.com",
        hash_contrasena=generar_hash_password("TemporalPassword123!"),
        rol_id_FK=1,
        estado="inactivo",
    )
    db_session.add_all([clinica_inactiva, admin_inactivo])
    db_session.commit()

    payload_webhook = {
        "id": "WH-PAYPAL-MOCK-999",
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": "I-SUB-PAYPAL-MOCK-999",
            "plan_id": "P-5CC29855SK5899208NLWUMWI",
            "custom_id": "99",
            "status": "ACTIVE",
            "subscriber": {
                "email_address": "admin.pendiente@vitalia-qa.com",
                "name": {
                    "given_name": "Admin",
                    "surname": "Pendiente",
                },
            },
        },
    }

    with patch("app.services.provisioning_service.enviar_correo_bienvenida_admin") as mock_email:
        mock_email.return_value = True

        respuesta = client.post("/api/webhooks/paypal", json=payload_webhook)
        assert respuesta.status_code == 200
        assert respuesta.json()["status"] == "success"
        assert respuesta.json()["clinica_id"] == 99

        db_session.refresh(clinica_inactiva)
        assert clinica_inactiva.activa is True
        assert clinica_inactiva.paypal_subscription_id == "I-SUB-PAYPAL-MOCK-999"

        db_session.refresh(admin_inactivo)
        assert admin_inactivo.estado == "activo"

        mock_email.assert_called_once()
