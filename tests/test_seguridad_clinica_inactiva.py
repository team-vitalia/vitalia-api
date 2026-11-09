import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import Base, get_db
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.main import app
from app.models.clinica import Clinica
from app.models.role import Role
from app.models.usuario import Usuario


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

    try:
        yield sesion
    finally:
        app.dependency_overrides.pop(get_db, None)
        sesion.close()
        Base.metadata.drop_all(motor)


@pytest.fixture
def cliente(sesion_db):
    return TestClient(app)


def test_login_rechazado_si_clinica_inactiva(sesion_db: Session, cliente: TestClient):
    clinica_inactiva = Clinica(
        nombre_comercial="Clínica Inactiva Test",
        plan_id_FK=1,
        activa=False,
    )
    sesion_db.add(clinica_inactiva)
    sesion_db.commit()
    sesion_db.refresh(clinica_inactiva)

    admin_usuario = Usuario(
        clinica_id_FK=clinica_inactiva.id_PK,
        nombre="Admin",
        apellido_paterno="Suspendido",
        correo_electronico="admin.suspendido@testclinica.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin_usuario)
    sesion_db.commit()

    respuesta = cliente.post(
        "/api/auth/login",
        json={
            "correo_electronico": "admin.suspendido@testclinica.com",
            "password": "PasswordSegura123!",
        },
    )

    assert respuesta.status_code == 403
    datos = respuesta.json()
    assert "access_token" not in datos
    assert "El acceso a esta clínica ha sido suspendido" in datos["detail"]


def test_token_revocado_al_desactivar_clinica(sesion_db: Session, cliente: TestClient):
    clinica = Clinica(
        nombre_comercial="Clínica Activa Test",
        plan_id_FK=1,
        activa=True,
    )
    sesion_db.add(clinica)
    sesion_db.commit()
    sesion_db.refresh(clinica)

    admin_usuario = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin",
        apellido_paterno="Activo",
        correo_electronico="admin.activo@testclinica.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin_usuario)
    sesion_db.commit()
    sesion_db.refresh(admin_usuario)

    token = crear_access_token(
        data={
            "sub": str(admin_usuario.id_PK),
            "correo": admin_usuario.correo_electronico,
            "rol_id": admin_usuario.rol_id_FK,
            "clinica_id": admin_usuario.clinica_id_FK,
        },
        clinica_id=admin_usuario.clinica_id_FK,
    )

    headers = {"Authorization": f"Bearer {token}"}

    respuesta_activa = cliente.get("/api/pacientes/", headers=headers)
    assert respuesta_activa.status_code == 200

    clinica.activa = False
    sesion_db.commit()

    respuesta_suspendida = cliente.get("/api/pacientes/", headers=headers)
    assert respuesta_suspendida.status_code == 403
    assert "El acceso a esta clínica ha sido suspendido" in respuesta_suspendida.json()["detail"]
