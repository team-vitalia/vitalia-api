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


def test_google_login_falla_sin_token(cliente: TestClient):
    respuesta = cliente.post("/api/auth/google-login", json={})
    assert respuesta.status_code == 400
    assert "token" in respuesta.json()["detail"].lower()


def test_google_login_falla_token_invalido(cliente: TestClient):
    respuesta = cliente.post("/api/auth/google-login", json={"token": "invalido-123"})
    assert respuesta.status_code == 401


def test_google_login_404_si_usuario_no_existe(cliente: TestClient):
    mock_token = "mock-google-token:usuario.no.existe@gmail.com:Usuario Desconocido"
    respuesta = cliente.post("/api/auth/google-login", json={"token": mock_token})
    assert respuesta.status_code == 404
    assert "No existe una cuenta registrada con este correo de Google" in respuesta.json()["detail"]


def test_google_login_exitoso_usuario_existente(sesion_db: Session, cliente: TestClient):
    clinica = sesion_db.query(Clinica).first()
    usuario_google = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Dr. Google",
        correo_electronico="doctor.google@gmail.com",
        hash_contrasena=None,
        auth_provider="google",
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(usuario_google)
    sesion_db.commit()

    mock_token = "mock-google-token:doctor.google@gmail.com:Dr. Google"
    respuesta = cliente.post("/api/auth/google-login", json={"token": mock_token})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert "access_token" in datos
    assert datos["token_type"] == "bearer"


def test_google_verify_endpoint(cliente: TestClient):
    mock_token = "mock-google-token:verificar@gmail.com:Juan Perez"
    respuesta = cliente.post("/api/auth/google-verify", json={"token": mock_token})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["email"] == "verificar@gmail.com"
    assert datos["name"] == "Juan Perez"


def test_preregistro_con_google_sin_password(sesion_db: Session, cliente: TestClient):
    payload = {
        "nombre_clinica": "Clínica Google Test",
        "nombre_admin": "Admin Google",
        "correo": "admin.google.test@clinica.com",
        "paypal_plan_id": "P-9JA53339DW996433FNLXJMJA",
        "auth_provider": "google",
    }
    respuesta = cliente.post("/api/suscripciones/pre-registro", json=payload)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["clinica_id"] > 0

    usuario = sesion_db.query(Usuario).filter(Usuario.correo_electronico == "admin.google.test@clinica.com").first()
    assert usuario is not None
    assert usuario.auth_provider == "google"
    assert usuario.hash_contrasena is None
