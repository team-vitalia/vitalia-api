"""Pruebas unitarias para los endpoints del panel de SuperAdmin (Fase 6)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import Base, get_db
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.main import app
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
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


def test_superadmin_deniega_acceso_a_usuarios_no_autorizados(sesion_db: Session, cliente: TestClient):
    """Verifica que un usuario sin rol de administrador recibe 403 al acceder a rutas de superadmin."""
    clinica_demo = sesion_db.query(Clinica).first()
    doctor_usuario = Usuario(
        clinica_id_FK=clinica_demo.id_PK,
        nombre="Dr. Perez",
        correo_electronico="doctor.perez@clinica.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=2,
        estado="activo",
    )
    sesion_db.add(doctor_usuario)
    sesion_db.commit()
    sesion_db.refresh(doctor_usuario)

    app.dependency_overrides[get_current_user] = lambda: doctor_usuario

    try:
        respuesta = cliente.get("/api/superadmin/clinicas")
        assert respuesta.status_code == 403
        assert "Acceso denegado" in respuesta.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_listar_clinicas_superadmin(sesion_db: Session, cliente: TestClient):
    """Verifica que el superadmin puede obtener el listado completo de clinicas con sus planes y administradores."""
    clinica_demo = sesion_db.query(Clinica).first()
    admin_usuario = Usuario(
        clinica_id_FK=clinica_demo.id_PK,
        nombre="Super",
        apellido_paterno="Admin",
        correo_electronico="superadmin@vitalia.com",
        hash_contrasena=generar_hash_password("SuperSecret123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(admin_usuario)
    sesion_db.commit()
    sesion_db.refresh(admin_usuario)

    app.dependency_overrides[get_current_user] = lambda: admin_usuario

    try:
        respuesta = cliente.get("/api/superadmin/clinicas")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert isinstance(datos, list)
        assert len(datos) >= 1
        primera = datos[0]
        assert "nombre_comercial" in primera
        assert "activa" in primera
        assert "plan" in primera
        assert "administradores" in primera
        assert len(primera["administradores"]) >= 1
        assert primera["administradores"][0]["correo_electronico"] == "superadmin@vitalia.com"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_actualizar_estado_clinica_suspender_y_activar(sesion_db: Session, cliente: TestClient):
    """Verifica que el superadmin puede suspender y posteriormente reactivar el acceso de una clinica."""
    clinica = sesion_db.query(Clinica).first()
    assert clinica.activa is True

    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin",
        correo_electronico="admin.central@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta_suspension = cliente.patch(
            f"/api/superadmin/clinicas/{clinica.id_PK}/estado",
            json={"activa": False},
        )
        assert respuesta_suspension.status_code == 200
        assert respuesta_suspension.json()["activa"] is False

        sesion_db.refresh(clinica)
        assert clinica.activa is False

        respuesta_reactivacion = cliente.patch(
            f"/api/superadmin/clinicas/{clinica.id_PK}/estado",
            json={"activa": True},
        )
        assert respuesta_reactivacion.status_code == 200
        assert respuesta_reactivacion.json()["activa"] is True

        sesion_db.refresh(clinica)
        assert clinica.activa is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_metricas_superadmin(sesion_db: Session, cliente: TestClient):
    """Verifica el calculo de metricas globales de suscripciones e ingresos mensuales."""
    clinica = sesion_db.query(Clinica).first()
    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin",
        correo_electronico="admin.metricas@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.get("/api/superadmin/metricas")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["total_clinicas"] >= 1
        assert datos["clinicas_activas"] >= 1
        assert datos["clinicas_inactivas"] == 0
        assert datos["ingresos_mensuales"] > 0
        assert datos["total_planes"] == 4
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_listar_planes_superadmin(sesion_db: Session, cliente: TestClient):
    """Verifica la consulta de planes y el conteo de clinicas suscritas activas."""
    clinica = sesion_db.query(Clinica).first()
    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin",
        correo_electronico="admin.planes@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.get("/api/superadmin/planes")
        assert respuesta.status_code == 200
        planes = respuesta.json()
        assert isinstance(planes, list)
        assert len(planes) == 4
        nombres = [p["nombre"] for p in planes]
        assert "Básico" in nombres
        assert "Clínica" in nombres
        assert "Profesional" in nombres
        assert "Empresarial" in nombres
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_obtener_metricas_clinica_individual(sesion_db: Session, cliente: TestClient):
    clinica = sesion_db.query(Clinica).first()
    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin Metricas",
        correo_electronico="admin.metricas@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.get(f"/api/superadmin/clinicas/{clinica.id_PK}/metricas")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["clinica_id"] == clinica.id_PK
        assert "uso_personal" in datos
        assert "uso_pacientes" in datos
        assert "uso_almacenamiento" in datos
        assert "citas_mes_actual" in datos
        assert "proximo_ciclo_facturacion" in datos
        assert "candidato_upsell" in datos
        assert isinstance(datos["motivos_upsell"], list)
        assert isinstance(datos["ultimos_accesos"], list)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_metricas_globales_expandidas(sesion_db: Session, cliente: TestClient):
    clinica = sesion_db.query(Clinica).first()
    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin Global",
        correo_electronico="admin.global@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.get("/api/superadmin/metricas")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert "ingresos_mensuales" in datos
        assert "proyeccion_anual" in datos
        assert "total_clinicas" in datos
        assert "clinicas_activas" in datos
        assert "clinicas_inactivas" in datos
        assert "usuarios_nuevos_mes" in datos
        assert "tasa_crecimiento_usuarios" in datos
        assert "historico_6_meses" in datos
        assert len(datos["historico_6_meses"]) == 6
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_forzar_actualizacion_plan_clinica(sesion_db: Session, cliente: TestClient):
    clinica = sesion_db.query(Clinica).first()
    planes = sesion_db.query(PlanSuscripcion).all()
    otro_plan = next(p for p in planes if p.id_PK != clinica.plan_id_FK)

    superadmin = Usuario(
        clinica_id_FK=clinica.id_PK,
        nombre="Admin Update Plan",
        correo_electronico="admin.updateplan@vitalia.com",
        hash_contrasena=generar_hash_password("PasswordSegura123!"),
        rol_id_FK=1,
        estado="activo",
    )
    sesion_db.add(superadmin)
    sesion_db.commit()

    app.dependency_overrides[get_current_user] = lambda: superadmin

    try:
        respuesta = cliente.patch(
            f"/api/superadmin/clinicas/{clinica.id_PK}/plan",
            json={"plan_id": otro_plan.id_PK},
        )
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["plan"]["id"] == otro_plan.id_PK
    finally:
        app.dependency_overrides.pop(get_current_user, None)
