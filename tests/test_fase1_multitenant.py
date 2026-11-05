from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.seeds import sembrar_planes_y_clinica_demo
from app.models.cita import Cita
from app.models.clinica import Clinica
from app.models.medicamento import Medicamento
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.sala import Sala
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

    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(motor)


def test_creacion_planes_suscripcion(sesion_db: Session):
    planes, demo = sembrar_planes_y_clinica_demo(sesion_db)

    assert len(planes) == 4

    basico = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Básico"
    ).first()
    assert basico is not None
    assert basico.precio_mensual == 599.0
    assert basico.precio_anual == 5990.0
    assert basico.limite_personal == 3
    assert basico.limite_pacientes == 100
    assert basico.incluye_calendar is False
    assert basico.incluye_correos is False
    assert basico.limite_ia_mensual == 0

    clinica_plan = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Clínica"
    ).first()
    assert clinica_plan is not None
    assert clinica_plan.precio_mensual == 1199.0
    assert clinica_plan.precio_anual == 11990.0
    assert clinica_plan.limite_personal == 10
    assert clinica_plan.limite_pacientes == 500
    assert clinica_plan.incluye_calendar is True
    assert clinica_plan.incluye_correos is True
    assert clinica_plan.limite_ia_mensual == 0

    profesional = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Profesional"
    ).first()
    assert profesional is not None
    assert profesional.precio_mensual == 2199.0
    assert profesional.precio_anual == 21990.0
    assert profesional.limite_personal == 20
    assert profesional.limite_pacientes == 1500
    assert profesional.incluye_calendar is True
    assert profesional.incluye_correos is True
    assert profesional.limite_ia_mensual == 100

    empresarial = sesion_db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Empresarial"
    ).first()
    assert empresarial is not None
    assert empresarial.precio_mensual == 4499.0
    assert empresarial.precio_anual == 44990.0
    assert empresarial.limite_personal == 30
    assert empresarial.limite_pacientes == 5000
    assert empresarial.incluye_calendar is True
    assert empresarial.incluye_correos is True
    assert empresarial.limite_ia_mensual == 500

    assert demo is not None
    assert demo.nombre_comercial == "Clínica Demo"
    assert demo.activa is True
    assert demo.plan_id_FK == empresarial.id_PK
    assert demo.plan.nombre == "Empresarial"


def test_restriccion_integridad_referencial_clinica_usuario(sesion_db: Session):
    _, demo = sembrar_planes_y_clinica_demo(sesion_db)

    with pytest.raises(IntegrityError):
        usuario_fk_inexistente = Usuario(
            clinica_id_FK=999999,
            nombre="Usuario Sin Tenant",
            correo_electronico="invalido@vitalia.com",
            hash_contrasena="hash_seguro_123",
            estado="activo",
        )
        sesion_db.add(usuario_fk_inexistente)
        sesion_db.commit()

    sesion_db.rollback()

    with pytest.raises(IntegrityError):
        usuario_sin_fk = Usuario(
            clinica_id_FK=None,
            nombre="Usuario Nulo",
            correo_electronico="nulo@vitalia.com",
            hash_contrasena="hash_seguro_123",
            estado="activo",
        )
        sesion_db.add(usuario_sin_fk)
        sesion_db.commit()

    sesion_db.rollback()

    usuario_valido = Usuario(
        clinica_id_FK=demo.id_PK,
        nombre="Usuario Valido",
        correo_electronico="valido@vitalia.com",
        hash_contrasena="hash_seguro_123",
        estado="activo",
    )
    sesion_db.add(usuario_valido)
    sesion_db.commit()

    assert usuario_valido.id_PK is not None
    assert usuario_valido.clinica_id_FK == demo.id_PK
    assert usuario_valido.clinica.nombre_comercial == "Clínica Demo"


def test_aislamiento_multitenant_consultas(sesion_db: Session):
    planes, _ = sembrar_planes_y_clinica_demo(sesion_db)
    plan_basico = planes[0]
    plan_clinica = planes[1]

    clinica_alfa = Clinica(
        nombre_comercial="Clínica Alfa",
        plan_id_FK=plan_basico.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    clinica_beta = Clinica(
        nombre_comercial="Clínica Beta",
        plan_id_FK=plan_clinica.id_PK,
        fecha_registro=datetime.now(),
        activa=True,
    )
    sesion_db.add_all([clinica_alfa, clinica_beta])
    sesion_db.commit()

    usuario_alfa = Usuario(
        clinica_id_FK=clinica_alfa.id_PK,
        nombre="Doctor Alfa",
        correo_electronico="doctor@alfa.com",
        hash_contrasena="clave_alfa",
    )
    usuario_beta = Usuario(
        clinica_id_FK=clinica_beta.id_PK,
        nombre="Doctor Beta",
        correo_electronico="doctor@beta.com",
        hash_contrasena="clave_beta",
    )

    paciente_alfa = Paciente(
        clinica_id_FK=clinica_alfa.id_PK,
        nombre="Paciente Alfa",
        apellido="Lopez",
    )
    paciente_beta = Paciente(
        clinica_id_FK=clinica_beta.id_PK,
        nombre="Paciente Beta",
        apellido="Perez",
    )

    sala_alfa = Sala(
        clinica_id_FK=clinica_alfa.id_PK,
        nombre="Sala Alfa 101",
    )
    sala_beta = Sala(
        clinica_id_FK=clinica_beta.id_PK,
        nombre="Sala Beta 201",
    )

    medicamento_alfa = Medicamento(
        clinica_id_FK=clinica_alfa.id_PK,
        nombre="Amoxicilina Alfa 500mg",
    )
    medicamento_beta = Medicamento(
        clinica_id_FK=clinica_beta.id_PK,
        nombre="Ibuprofeno Beta 400mg",
    )

    cita_alfa = Cita(
        clinica_id_FK=clinica_alfa.id_PK,
        fecha=date(2026, 11, 6),
        motivo="Consulta Alfa",
    )
    cita_beta = Cita(
        clinica_id_FK=clinica_beta.id_PK,
        fecha=date(2026, 11, 7),
        motivo="Consulta Beta",
    )

    sesion_db.add_all([
        usuario_alfa, usuario_beta,
        paciente_alfa, paciente_beta,
        sala_alfa, sala_beta,
        medicamento_alfa, medicamento_beta,
        cita_alfa, cita_beta,
    ])
    sesion_db.commit()

    usuarios_c1 = sesion_db.query(Usuario).filter(Usuario.clinica_id == clinica_alfa.id_PK).all()
    assert len(usuarios_c1) == 1
    assert usuarios_c1[0].nombre == "Doctor Alfa"
    assert usuario_beta not in usuarios_c1

    pacientes_c1 = sesion_db.query(Paciente).filter(Paciente.clinica_id == clinica_alfa.id_PK).all()
    assert len(pacientes_c1) == 1
    assert pacientes_c1[0].nombre == "Paciente Alfa"
    assert paciente_beta not in pacientes_c1

    salas_c1 = sesion_db.query(Sala).filter(Sala.clinica_id == clinica_alfa.id_PK).all()
    assert len(salas_c1) == 1
    assert salas_c1[0].nombre == "Sala Alfa 101"
    assert sala_beta not in salas_c1

    medicamentos_c1 = sesion_db.query(Medicamento).filter(Medicamento.clinica_id == clinica_alfa.id_PK).all()
    assert len(medicamentos_c1) == 1
    assert medicamentos_c1[0].nombre == "Amoxicilina Alfa 500mg"
    assert medicamento_beta not in medicamentos_c1

    citas_c1 = sesion_db.query(Cita).filter(Cita.clinica_id == clinica_alfa.id_PK).all()
    assert len(citas_c1) == 1
    assert citas_c1[0].motivo == "Consulta Alfa"
    assert cita_beta not in citas_c1

    usuarios_c2 = sesion_db.query(Usuario).filter(Usuario.clinica_id == clinica_beta.id_PK).all()
    assert len(usuarios_c2) == 1
    assert usuarios_c2[0].nombre == "Doctor Beta"
    assert usuario_alfa not in usuarios_c2

    pacientes_c2 = sesion_db.query(Paciente).filter(Paciente.clinica_id == clinica_beta.id_PK).all()
    assert len(pacientes_c2) == 1
    assert pacientes_c2[0].nombre == "Paciente Beta"
    assert paciente_alfa not in pacientes_c2

    salas_c2 = sesion_db.query(Sala).filter(Sala.clinica_id == clinica_beta.id_PK).all()
    assert len(salas_c2) == 1
    assert salas_c2[0].nombre == "Sala Beta 201"
    assert sala_alfa not in salas_c2

    medicamentos_c2 = sesion_db.query(Medicamento).filter(Medicamento.clinica_id == clinica_beta.id_PK).all()
    assert len(medicamentos_c2) == 1
    assert medicamentos_c2[0].nombre == "Ibuprofeno Beta 400mg"
    assert medicamento_alfa not in medicamentos_c2

    citas_c2 = sesion_db.query(Cita).filter(Cita.clinica_id == clinica_beta.id_PK).all()
    assert len(citas_c2) == 1
    assert citas_c2[0].motivo == "Consulta Beta"
    assert cita_alfa not in citas_c2

    assert len(sesion_db.query(Usuario).filter(Usuario.clinica_id_FK == clinica_alfa.id_PK).all()) == 1
    assert len(sesion_db.query(Paciente).filter(Paciente.clinica_id_FK == clinica_alfa.id_PK).all()) == 1
    assert len(sesion_db.query(Sala).filter(Sala.clinica_id_FK == clinica_alfa.id_PK).all()) == 1
    assert len(sesion_db.query(Medicamento).filter(Medicamento.clinica_id_FK == clinica_alfa.id_PK).all()) == 1
    assert len(sesion_db.query(Cita).filter(Cita.clinica_id_FK == clinica_alfa.id_PK).all()) == 1
