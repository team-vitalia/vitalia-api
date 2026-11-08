"""Reglas de acceso a información clínica (expediente, consultas, recetas).

Un doctor puede ver a un paciente de su clínica si:
  * tiene (o tuvo) citas con él, o
  * le registró una consulta, o
  * el paciente le fue transferido (transferencias_paciente).
Administrador y coordinador: cualquier paciente de su clínica.
Paciente: solo su propio expediente.
Recepción y almacén: NO acceden al expediente clínico.
"""
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
    return False


def puede_ver_paciente(db: Session, usuario, paciente: Paciente) -> bool:
    """¿Puede el usuario ver información clínica de este paciente?"""
    rol = usuario.rol_id_FK
    clinica = clinica_de(usuario)
    if clinica is not None and paciente.clinica_id_FK != clinica:
        return False

    if rol in (ROL_ADMIN, ROL_COORDINADOR):
        return True
    if rol == ROL_PACIENTE:
        return paciente.usuario_id_FK == usuario.id_PK
    if rol == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario)
        return bool(doctor and doctor_tiene_relacion(db, doctor.id_PK, paciente.id_PK))
    return False


def nombre_completo(paciente: Paciente | None) -> str | None:
    if not paciente:
        return None
    partes = [paciente.nombre, paciente.apellido_paterno or paciente.apellido, paciente.apellido_materno]
    return " ".join(p for p in partes if p) or None
