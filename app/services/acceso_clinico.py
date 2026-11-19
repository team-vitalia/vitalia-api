from sqlalchemy.orm import Session

from app.core.roles import (
    ROL_ADMIN, ROL_COORDINADOR, ROL_DOCTOR, ROL_PACIENTE, clinica_de,
)
from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.doctor import Doctor
from app.models.paciente import Paciente
from app.models.transferencia_paciente import TransferenciaPaciente


def doctor_de_usuario(db: Session, usuario) -> Doctor | None:
    return db.query(Doctor).filter(Doctor.usuario_id_FK == usuario.id_PK).first()


def paciente_de_usuario(db: Session, usuario) -> Paciente | None:
    return db.query(Paciente).filter(Paciente.usuario_id_FK == usuario.id_PK).first()


def _clinica_es_gratuito(db: Session, usuario) -> bool:
    if not usuario:
        return False
    clinica_obj = getattr(usuario, "clinica", None)
    if clinica_obj and getattr(clinica_obj, "plan", None):
        return (clinica_obj.plan.nombre or "").lower().strip() == "gratuito"
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.models.clinica import Clinica
        from app.models.plan_suscripcion import PlanSuscripcion
        plan_nombre = (
            db.query(PlanSuscripcion.nombre)
            .join(Clinica, Clinica.plan_id_FK == PlanSuscripcion.id_PK)
            .filter(Clinica.id_PK == clinica_id)
            .scalar()
        )
        return bool(plan_nombre and plan_nombre.strip().lower() == "gratuito")
    return False


def doctor_tiene_relacion(db: Session, doctor_id: int, paciente_id: int) -> bool:
    if db.query(Cita.id_PK).filter(
        Cita.doctor_id_FK == doctor_id, Cita.paciente_id_FK == paciente_id
    ).first():
        return True
    if db.query(Consulta.id_PK).filter(
        Consulta.doctor_id_FK == doctor_id, Consulta.paciente_id_FK == paciente_id
    ).first():
        return True
    if db.query(TransferenciaPaciente.id_PK).filter(
        TransferenciaPaciente.doctor_destino_id_FK == doctor_id,
        TransferenciaPaciente.paciente_id_FK == paciente_id,
    ).first():
        return True
    doctor = db.query(Doctor).filter(Doctor.id_PK == doctor_id).first()
    paciente = db.query(Paciente).filter(Paciente.id_PK == paciente_id).first()
    if doctor and paciente and doctor.usuario and doctor.usuario.clinica_id_FK == paciente.clinica_id_FK:
        if _clinica_es_gratuito(db, doctor.usuario):
            return True
    return False


def puede_ver_paciente(db: Session, usuario, paciente: Paciente) -> bool:
    rol = getattr(usuario, "rol_id_FK", None)
    clinica = clinica_de(usuario)
    if clinica is not None and paciente.clinica_id_FK != clinica:
        return False

    if rol in (ROL_ADMIN, ROL_COORDINADOR):
        return True
    if rol == ROL_PACIENTE:
        return paciente.usuario_id_FK == getattr(usuario, "id_PK", None)
    if rol == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario)
        if not doctor:
            return False
        if _clinica_es_gratuito(db, usuario):
            return True
        return bool(doctor_tiene_relacion(db, doctor.id_PK, paciente.id_PK))
    return False


def nombre_completo(paciente: Paciente | None) -> str | None:
    if not paciente:
        return None
    partes = [paciente.nombre, paciente.apellido_paterno or paciente.apellido, paciente.apellido_materno]
    return " ".join(p for p in partes if p) or None
