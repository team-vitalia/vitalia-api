from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.clinica import Clinica
from app.models.usuario import Usuario

APELLIDOS = [
    "Perez", "Garcia", "Lopez", "Rodriguez", "Hernandez",
    "Sanchez", "Martinez", "Gonzalez", "Diaz", "Torres",
    "Morales", "Vargas", "Romero", "Alvarez", "Castillo",
    "Mendoza", "Ruiz", "Gutierrez", "Navarro", "Soto",
    "Aguilar", "Medina", "Vega", "Rojas", "Cruz",
]


@pytest.fixture
def cliente(sesion_db):
    return TestClient(app)


def test_registro_gratuito_inmediato_clinica_activa(sesion_db: Session, cliente: TestClient):
    payload = {
        "nombre_doctor": "Dr. Roberto Casas",
        "nombre_clinica": "Consultorio Medico Casas",
        "correo": "dr.casas@vitalia.com",
        "password": "PasswordSegura123!",
    }

    respuesta = cliente.post("/api/suscripciones/registro-gratuito", json=payload)
    assert respuesta.status_code == 201

    datos = respuesta.json()
    assert datos["status"] == "success"
    assert "access_token" in datos
    assert datos["nombre_plan"] == "Gratuito"

    clinica_id = datos["clinica_id"]
    clinica = sesion_db.query(Clinica).filter(Clinica.id_PK == clinica_id).first()
    assert clinica is not None
    assert clinica.activa is True
    assert clinica.paypal_subscription_id is None
    assert clinica.plan.nombre == "Gratuito"

    usuario = sesion_db.query(Usuario).filter(Usuario.clinica_id_FK == clinica_id).first()
    assert usuario is not None
    assert usuario.rol_id_FK == 2
    assert usuario.estado == "activo"


def test_doctor_gratuito_limite_20_pacientes_mes(sesion_db: Session, cliente: TestClient):
    registro = cliente.post(
        "/api/suscripciones/registro-gratuito",
        json={
            "nombre_doctor": "Dra. Ana Fuentes",
            "nombre_clinica": "Clinica Gratuita Fuentes",
            "correo": "dra.fuentes@vitalia.com",
            "password": "PasswordSegura123!",
        },
    )
    assert registro.status_code == 201
    token = registro.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(1, 21):
        apellido = APELLIDOS[i - 1]
        payload_paciente = {
            "nombre": f"Paciente{apellido}",
            "apellido": apellido,
            "apellido_paterno": apellido,
            "curp": f"PACA9001{i:02d}HDFRRN{i:02d}",
            "fecha_nacimiento": "1990-01-01",
            "genero": "Masculino" if i % 2 == 0 else "Femenino",
            "correo_electronico": f"paciente_{apellido.lower()}@test.com",
        }
        res_paciente = cliente.post("/api/pacientes/", headers=headers, json=payload_paciente)
        assert res_paciente.status_code == 201

    apellido_21 = APELLIDOS[20]
    payload_paciente_21 = {
        "nombre": f"Paciente{apellido_21}",
        "apellido": apellido_21,
        "apellido_paterno": apellido_21,
        "curp": "PACA900121HDFRRN21",
        "fecha_nacimiento": "1990-01-01",
        "genero": "Femenino",
        "correo_electronico": f"paciente_{apellido_21.lower()}@test.com",
    }
    res_paciente_21 = cliente.post("/api/pacientes/", headers=headers, json=payload_paciente_21)
    assert res_paciente_21.status_code == 403


def test_doctor_gratuito_bloqueo_crear_usuario_y_acceso_salas(sesion_db: Session, cliente: TestClient):
    registro = cliente.post(
        "/api/suscripciones/registro-gratuito",
        json={
            "nombre_doctor": "Dr. Carlos Ramos",
            "nombre_clinica": "Consultorio Ramos",
            "correo": "dr.ramos@vitalia.com",
            "password": "PasswordSegura123!",
        },
    )
    assert registro.status_code == 201
    token = registro.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload_usuario = {
        "nombre": "Enfermera",
        "apellido_paterno": "Perez",
        "correo_electronico": "enfermera.ramos@vitalia.com",
        "password": "PasswordSegura123!",
        "rol_id_FK": 4,
    }
    res_usuario = cliente.post("/api/usuarios/", headers=headers, json=payload_usuario)
    assert res_usuario.status_code == 403

    res_salas = cliente.get("/api/salas", headers=headers)
    assert res_salas.status_code == 403

    res_almacen = cliente.get("/api/almacen/medicamentos", headers=headers)
    assert res_almacen.status_code == 403

    res_reportes = cliente.get("/api/reportes/ocupacion-salas", headers=headers)
    assert res_reportes.status_code == 403

    res_auditoria = cliente.get("/api/auditoria", headers=headers)
    assert res_auditoria.status_code == 403

    res_contratos = cliente.get("/api/contratos", headers=headers)
    assert res_contratos.status_code == 403


def test_doctor_gratuito_asignacion_automatica_y_bloqueo_en_pago(sesion_db: Session, cliente: TestClient):
    from app.core.security import crear_access_token
    from app.models.plan_suscripcion import PlanSuscripcion
    from app.models.doctor import Doctor

    reg_gratuito = cliente.post(
        "/api/suscripciones/registro-gratuito",
        json={
            "nombre_doctor": "Dr. Fernando Soto",
            "nombre_clinica": "Consultorio Soto",
            "correo": "dr.soto@vitalia.com",
            "password": "PasswordSegura123!",
        },
    )
    assert reg_gratuito.status_code == 201
    token_gratuito = reg_gratuito.json()["access_token"]
    headers_gratuito = {"Authorization": f"Bearer {token_gratuito}"}

    res_crear_paciente = cliente.post(
        "/api/pacientes/",
        headers=headers_gratuito,
        json={
            "nombre": "Mariana",
            "apellido": "Torres",
            "apellido_paterno": "Torres",
            "curp": "TORM950505HDFRRN01",
            "correo_electronico": "mariana.torres@example.com",
        },
    )
    assert res_crear_paciente.status_code == 201
    paciente_gratuito_id = res_crear_paciente.json()["id_PK"]

    res_expediente_gratuito = cliente.get(
        f"/api/expediente/paciente/{paciente_gratuito_id}",
        headers=headers_gratuito,
    )
    assert res_expediente_gratuito.status_code == 200
    assert res_expediente_gratuito.json()["paciente"]["id_PK"] == paciente_gratuito_id

    res_antecedente = cliente.post(
        f"/api/expediente/paciente/{paciente_gratuito_id}/antecedentes",
        headers=headers_gratuito,
        json={"tipo_sangre": "O+", "descripcion": "Sin antecedentes patologicos"},
    )
    assert res_antecedente.status_code == 201

    res_mis_pacientes = cliente.get("/api/doctores/mis-pacientes", headers=headers_gratuito)
    assert res_mis_pacientes.status_code == 200
    lista_pacientes = res_mis_pacientes.json()
    assert len(lista_pacientes) == 1
    assert lista_pacientes[0]["nombre"] == "Mariana"
    assert lista_pacientes[0]["apellido"] == "Torres"

    res_transferir_gratuito = cliente.get("/api/doctores/lista-para-transferir", headers=headers_gratuito)
    assert res_transferir_gratuito.status_code == 200
    assert res_transferir_gratuito.json() == []

    res_agendar_gratuito = cliente.post(
        "/api/citas/",
        headers=headers_gratuito,
        json={
            "paciente_id_FK": paciente_gratuito_id,
            "doctor_id_FK": 0,
            "fecha": "2026-11-20",
            "hora_inicio": "10:00:00",
            "hora_fin": "10:30:00",
            "motivo": "Consulta general",
        },
    )
    assert res_agendar_gratuito.status_code == 201
    assert res_agendar_gratuito.json()["paciente_id_FK"] == paciente_gratuito_id

    plan_pago = sesion_db.query(PlanSuscripcion).filter(PlanSuscripcion.nombre == "Básico").first()
    clinica_pago = Clinica(
        nombre_comercial="Clinica Pago Integral",
        plan_id_FK=plan_pago.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add(clinica_pago)
    sesion_db.flush()

    doc_usuario_pago = Usuario(
        clinica_id_FK=clinica_pago.id_PK,
        nombre="Dr. Pago",
        correo_electronico="dr.pago@example.com",
        rol_id_FK=2,
        estado="activo",
    )
    sesion_db.add(doc_usuario_pago)
    sesion_db.flush()

    perfil_doc_pago = Doctor(usuario_id_FK=doc_usuario_pago.id_PK, estado="activo")
    sesion_db.add(perfil_doc_pago)
    sesion_db.commit()

    token_doc_pago = crear_access_token(
        data={"sub": str(doc_usuario_pago.id_PK), "rol_id": 2},
        clinica_id=clinica_pago.id_PK,
    )
    headers_doc_pago = {"Authorization": f"Bearer {token_doc_pago}"}

    res_doc_pago_crear = cliente.post(
        "/api/pacientes/",
        headers=headers_doc_pago,
        json={
            "nombre": "Pedro",
            "apellido": "Ramirez",
            "apellido_paterno": "Ramirez",
            "curp": "RAMP900101HDFRRN99",
            "correo_electronico": "pedro.ramirez@example.com",
        },
    )
    assert res_doc_pago_crear.status_code == 403
    assert "En planes de pago" in res_doc_pago_crear.json()["detail"]

    res_doc_pago_agendar = cliente.post(
        "/api/citas/",
        headers=headers_doc_pago,
        json={
            "paciente_id_FK": paciente_gratuito_id,
            "doctor_id_FK": perfil_doc_pago.id_PK,
            "fecha": "2026-11-20",
            "hora_inicio": "10:00:00",
            "hora_fin": "10:30:00",
            "motivo": "Consulta general",
        },
    )
    assert res_doc_pago_agendar.status_code == 403


def test_asistente_ia_bloqueado_en_plan_gratuito(sesion_db: Session, cliente: TestClient):
    from app.models.doctor import Doctor
    from app.models.usuario import Usuario

    reg_gratuito = cliente.post(
        "/api/suscripciones/registro-gratuito",
        json={
            "nombre_doctor": "Dr. Carlos Trejo",
            "nombre_clinica": "Consultorio Trejo",
            "correo": "dr.trejo@vitalia.com",
            "password": "PasswordSegura123!",
        },
    )
    assert reg_gratuito.status_code == 201
    token_gratuito = reg_gratuito.json()["access_token"]
    headers_gratuito = {"Authorization": f"Bearer {token_gratuito}"}

    res_paciente = cliente.post(
        "/api/pacientes/",
        headers=headers_gratuito,
        json={
            "nombre": "Esteban",
            "apellido": "Gomez",
            "apellido_paterno": "Gomez",
            "curp": "GOME900101HDFRRN01",
            "correo_electronico": "esteban.gomez@example.com",
        },
    )
    assert res_paciente.status_code == 201
    paciente_id = res_paciente.json()["id_PK"]

    doctor_db = sesion_db.query(Doctor).join(Usuario, Doctor.usuario_id_FK == Usuario.id_PK).filter(Usuario.correo_electronico == "dr.trejo@vitalia.com").first()
    assert doctor_db is not None

    res_cita = cliente.post(
        "/api/citas/",
        headers=headers_gratuito,
        json={
            "paciente_id_FK": paciente_id,
            "doctor_id_FK": doctor_db.id_PK,
            "fecha": "2026-11-20",
            "hora_inicio": "11:00:00",
            "hora_fin": "11:30:00",
            "motivo": "Dolor abdominal agudo",
        },
    )
    assert res_cita.status_code == 201
    cita_id = res_cita.json()["id_PK"]

    res_ia = cliente.post(
        f"/api/citas/{cita_id}/asistente-ia",
        headers=headers_gratuito,
        json={
            "sintomas": "Dolor abdominal en fosa iliaca derecha con fiebre y nauseas",
            "incluir_notas_previas": False,
        },
    )
    assert res_ia.status_code == 403
    assert "El Asistente Clínico IA requiere un plan Profesional o Empresarial." in res_ia.json()["detail"]

