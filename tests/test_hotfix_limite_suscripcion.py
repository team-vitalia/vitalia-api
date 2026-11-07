from datetime import datetime
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.services.suscripcion_service import (
    verificar_limite_pacientes,
    verificar_limite_personal,
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
    return TestClient(app)


def test_hotfix_limite_personal_no_bloquea_creacion_paciente(sesion_db: Session, cliente: TestClient):
    plan_basico = PlanSuscripcion(
        nombre="Básico",
        precio_mensual=599.0,
        precio_anual=5990.0,
        limite_personal=3,
        limite_pacientes=100,
        incluye_calendar=False,
        incluye_correos=False,
        limite_ia_mensual=0,
        limite_sucursales=1,
    )
    sesion_db.add(plan_basico)
    sesion_db.flush()

    clinica = Clinica(
        nombre_comercial="Clínica Vitalia Test",
        plan_id_FK=plan_basico.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    hash_pw = generar_hash_password("PasswordSegura123!")

    admin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin",
        apellido_paterno="Principal",
        correo_electronico="admin.test@vitalia.com",
        hash_contrasena=hash_pw,
        rol_id_FK=1,
        estado="activo",
    )
    doctor = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Doctor",
        apellido_paterno="General",
        correo_electronico="doctor.test@vitalia.com",
        hash_contrasena=hash_pw,
        rol_id_FK=2,
        estado="activo",
    )
    recepcion = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Recepcion",
        apellido_paterno="Front",
        correo_electronico="recepcion.test@vitalia.com",
        hash_contrasena=hash_pw,
        rol_id_FK=4,
        estado="activo",
    )
    sesion_db.add_all([admin, doctor, recepcion])
    sesion_db.commit()

    with pytest.raises(HTTPException) as exc_personal:
        verificar_limite_personal(sesion_db, clinica.id_PK)
    assert exc_personal.value.status_code == 403

    verificar_limite_pacientes(sesion_db, clinica.id_PK)

    token_admin = crear_access_token(
        data={"sub": str(admin.id_PK), "rol_id": 1},
        clinica_id=clinica.id_PK,
    )

    payload_paciente = {
        "nombre": "Carlos",
        "apellido_paterno": "Gomez",
        "correo_electronico": "carlos.paciente@vitalia.com",
        "password": "PasswordSegura123!",
        "rol_id_FK": 3,
        "curp": "GOCC900101HDFRRN01",
    }
    respuesta_paciente = cliente.post(
        "/api/usuarios/",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_paciente,
    )
    assert respuesta_paciente.status_code == 201
    datos_paciente = respuesta_paciente.json()
    assert datos_paciente["rol_id_FK"] == 3

    payload_cuarto_personal = {
        "nombre": "Enfermera",
        "apellido_paterno": "Suarez",
        "correo_electronico": "enfermera.cuarta@vitalia.com",
        "password": "PasswordSegura123!",
        "rol_id_FK": 4,
    }
    respuesta_cuarto = cliente.post(
        "/api/usuarios/",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_cuarto_personal,
    )
    assert respuesta_cuarto.status_code == 403
    assert "Límite de personal alcanzado" in respuesta_cuarto.json()["detail"]

    payload_paciente_directo = {
        "nombre": "Maria",
        "apellido": "Lopez",
        "apellido_paterno": "Lopez",
        "correo_electronico": "maria.paciente@vitalia.com",
        "curp": "LOPM920202MDFRRN02",
        "fecha_nacimiento": "1992-02-02",
        "genero": "Femenino",
    }
    respuesta_paciente_directo = cliente.post(
        "/api/pacientes/",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_paciente_directo,
    )
    assert respuesta_paciente_directo.status_code == 201
