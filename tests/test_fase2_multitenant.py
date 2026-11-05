from datetime import date, datetime

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.services.suscripcion_service import (
    validar_limite_pacientes,
    validar_limite_personal,
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


def test_jwt_incluye_tenant_y_get_current_user_lo_extrae(sesion_db: Session):
    plan = PlanSuscripcion(
        nombre="Plan Demo",
        precio_mensual=100.0,
        precio_anual=1000.0,
        limite_personal=5,
        limite_pacientes=100,
        incluye_calendar=True,
        incluye_correos=True,
        limite_ia_mensual=10,
        limite_sucursales=1,
    )
    sesion_db.add(plan)
    sesion_db.flush()

    clinica = Clinica(
        nombre_comercial="Clínica San José",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    usuario = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Dr. San José",
        correo_electronico="sanjose@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(usuario)
    sesion_db.commit()

    token = crear_access_token(
        data={
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK,
        },
        clinica_id=clinica.id_PK,
    )

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload.get("clinica_id") == clinica.id_PK
    assert payload.get("sub") == str(usuario.id_PK)

    credenciales = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    usuario_obtenido = get_current_user(credenciales, sesion_db)

    assert usuario_obtenido.id_PK == usuario.id_PK
    assert usuario_obtenido.clinica_id_FK == clinica.id_PK
    assert usuario_obtenido.clinica_id == clinica.id_PK


def test_limite_plan_basico_bloquea_cuarto_usuario_403(sesion_db: Session, cliente: TestClient):
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

    clinica_basica = Clinica(
        nombre_comercial="Clínica Básica",
        plan_id_FK=plan_basico.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add(clinica_basica)
    sesion_db.flush()

    admin = Usuario(
        clinica_id_FK=clinica_basica.id_PK,
        nombre="Admin Básico",
        correo_electronico="admin.basico@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=1,
        estado="activo",
    )
    usuario_2 = Usuario(
        clinica_id_FK=clinica_basica.id_PK,
        nombre="Doctor 1",
        correo_electronico="doc1@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=2,
        estado="activo",
    )
    usuario_3 = Usuario(
        clinica_id_FK=clinica_basica.id_PK,
        nombre="Doctor 2",
        correo_electronico="doc2@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=2,
        estado="activo",
    )
    sesion_db.add_all([admin, usuario_2, usuario_3])
    sesion_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        validar_limite_personal(sesion_db, clinica_basica.id_PK)
    assert exc_info.value.status_code == 403

    token_admin = crear_access_token(
        data={"sub": str(admin.id_PK), "rol_id": 1},
        clinica_id=clinica_basica.id_PK,
    )

    respuesta = cliente.post(
        "/api/usuarios/",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "nombre": "Cuarto Usuario",
            "apellido_paterno": "Perez",
            "correo_electronico": "cuarto@vitalia.com",
            "password": "Password123!",
            "rol_id_FK": 2,
        },
    )

    assert respuesta.status_code == 403


def test_aislamiento_multitenant_consultas_pacientes(sesion_db: Session, cliente: TestClient):
    plan = PlanSuscripcion(
        nombre="Plan Corporativo",
        precio_mensual=2000.0,
        precio_anual=20000.0,
        limite_personal=50,
        limite_pacientes=1000,
        incluye_calendar=True,
        incluye_correos=True,
        limite_ia_mensual=100,
        limite_sucursales=5,
    )
    sesion_db.add(plan)
    sesion_db.flush()

    clinica_1 = Clinica(
        nombre_comercial="Clínica Uno",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    clinica_2 = Clinica(
        nombre_comercial="Clínica Dos",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add_all([clinica_1, clinica_2])
    sesion_db.flush()

    admin_clinica_1 = Usuario(
        clinica_id_FK=clinica_1.id_PK,
        nombre="Admin Clínica 1",
        correo_electronico="admin1@clinica1.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=1,
        estado="activo",
    )
    admin_clinica_2 = Usuario(
        clinica_id_FK=clinica_2.id_PK,
        nombre="Admin Clínica 2",
        correo_electronico="admin2@clinica2.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=1,
        estado="activo",
    )
    paciente_a = Paciente(
        clinica_id_FK=clinica_1.id_PK,
        nombre="Paciente A",
        apellido="Clinica Uno",
        apellido_paterno="Clinica",
        curp="PACA010101HDFRRN01",
        fecha_nacimiento=date(1990, 1, 1),
        genero="Masculino",
        estado="activo",
    )
    sesion_db.add_all([admin_clinica_1, admin_clinica_2, paciente_a])
    sesion_db.commit()

    token_clinica_2 = crear_access_token(
        data={"sub": str(admin_clinica_2.id_PK), "rol_id": 1},
        clinica_id=clinica_2.id_PK,
    )

    respuesta_listado = cliente.get(
        "/api/pacientes/",
        headers={"Authorization": f"Bearer {token_clinica_2}"},
    )
    assert respuesta_listado.status_code == 200
    ids_obtenidos = [p["id_PK"] for p in respuesta_listado.json()]
    assert paciente_a.id_PK not in ids_obtenidos
    assert len(respuesta_listado.json()) == 0

    respuesta_detalle = cliente.get(
        f"/api/pacientes/{paciente_a.id_PK}",
        headers={"Authorization": f"Bearer {token_clinica_2}"},
    )
    assert respuesta_detalle.status_code == 404

    token_clinica_1 = crear_access_token(
        data={"sub": str(admin_clinica_1.id_PK), "rol_id": 1},
        clinica_id=clinica_1.id_PK,
    )
    respuesta_detalle_autorizado = cliente.get(
        f"/api/pacientes/{paciente_a.id_PK}",
        headers={"Authorization": f"Bearer {token_clinica_1}"},
    )
    assert respuesta_detalle_autorizado.status_code == 200
    assert respuesta_detalle_autorizado.json()["nombre"] == "Paciente A"


def test_creacion_asigna_automaticamente_tenant_del_usuario_en_sesion(
    sesion_db: Session, cliente: TestClient
):
    plan = PlanSuscripcion(
        nombre="Plan General",
        precio_mensual=500.0,
        precio_anual=5000.0,
        limite_personal=10,
        limite_pacientes=100,
        incluye_calendar=True,
        incluye_correos=True,
        limite_ia_mensual=10,
        limite_sucursales=1,
    )
    sesion_db.add(plan)
    sesion_db.flush()

    clinica_origen = Clinica(
        nombre_comercial="Clínica Origen",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    clinica_otra = Clinica(
        nombre_comercial="Clínica Otra",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add_all([clinica_origen, clinica_otra])
    sesion_db.flush()

    admin = Usuario(
        clinica_id_FK=clinica_origen.id_PK,
        nombre="Admin Origen",
        correo_electronico="admin.origen@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin)
    sesion_db.commit()

    token = crear_access_token(
        data={"sub": str(admin.id_PK), "rol_id": 1},
        clinica_id=clinica_origen.id_PK,
    )

    respuesta_paciente = cliente.post(
        "/api/pacientes/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Nuevo Paciente",
            "apellido": "Gomez",
            "apellido_paterno": "Gomez",
            "curp": "GOMN020202HDFRRN02",
            "fecha_nacimiento": "1995-05-10",
            "genero": "Masculino",
            "clinica_id_FK": clinica_otra.id_PK,
        },
    )
    assert respuesta_paciente.status_code == 201
    paciente_creado = sesion_db.query(Paciente).filter(
        Paciente.id_PK == respuesta_paciente.json()["id_PK"]
    ).first()
    assert paciente_creado.clinica_id_FK == clinica_origen.id_PK
    assert paciente_creado.clinica_id_FK != clinica_otra.id_PK

    respuesta_usuario = cliente.post(
        "/api/usuarios/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Nuevo Doctor",
            "apellido_paterno": "Ruiz",
            "correo_electronico": "doctor.ruiz@vitalia.com",
            "password": "Password123!",
            "rol_id_FK": 2,
            "clinica_id_FK": clinica_otra.id_PK,
        },
    )
    assert respuesta_usuario.status_code == 201
    usuario_creado = sesion_db.query(Usuario).filter(
        Usuario.id_PK == respuesta_usuario.json()["id_PK"]
    ).first()
    assert usuario_creado.clinica_id_FK == clinica_origen.id_PK
    assert usuario_creado.clinica_id_FK != clinica_otra.id_PK


def test_validador_limite_pacientes_bloquea_exceso_403(sesion_db: Session, cliente: TestClient):
    plan = PlanSuscripcion(
        nombre="Plan Pacientes 2",
        precio_mensual=300.0,
        precio_anual=3000.0,
        limite_personal=10,
        limite_pacientes=2,
        incluye_calendar=False,
        incluye_correos=False,
        limite_ia_mensual=0,
        limite_sucursales=1,
    )
    sesion_db.add(plan)
    sesion_db.flush()

    clinica = Clinica(
        nombre_comercial="Clínica Pacientes",
        plan_id_FK=plan.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add(clinica)
    sesion_db.flush()

    recepcion = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Recepcionista",
        correo_electronico="recep@vitalia.com",
        hash_contrasena=generar_hash_password("Pass123!"),
        rol_id_FK=4,
        estado="activo",
    )
    paciente_1 = Paciente(
        clinica_id_FK=clinica.id_PK,
        nombre="P1",
        apellido="Uno",
        apellido_paterno="Uno",
        curp="UNOP010101HDFRRN01",
        fecha_nacimiento=date(1991, 1, 1),
        genero="Femenino",
        estado="activo",
    )
    paciente_2 = Paciente(
        clinica_id_FK=clinica.id_PK,
        nombre="P2",
        apellido="Dos",
        apellido_paterno="Dos",
        curp="DOSP020202HDFRRN02",
        fecha_nacimiento=date(1992, 2, 2),
        genero="Femenino",
        estado="activo",
    )
    sesion_db.add_all([recepcion, paciente_1, paciente_2])
    sesion_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        validar_limite_pacientes(sesion_db, clinica.id_PK)
    assert exc_info.value.status_code == 403

    token_recep = crear_access_token(
        data={"sub": str(recepcion.id_PK), "rol_id": 4},
        clinica_id=clinica.id_PK,
    )
    respuesta = cliente.post(
        "/api/pacientes/",
        headers={"Authorization": f"Bearer {token_recep}"},
        json={
            "nombre": "P3 Excedente",
            "apellido": "Tres",
            "apellido_paterno": "Tres",
            "curp": "TOEP030303HDFRRN03",
            "fecha_nacimiento": "1993-03-03",
            "genero": "Femenino",
        },
    )
    assert respuesta.status_code == 403
