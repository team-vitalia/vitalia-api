from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class TransferenciaPaciente(Base):
    """Historial de transferencias de un paciente entre médicos (patient_doctor_history)."""

    __tablename__ = "transferencias_paciente"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    clinica_id_FK: Mapped[int] = mapped_column(ForeignKey("clinicas.id_PK"), nullable=False)
    paciente_id_FK: Mapped[int] = mapped_column(ForeignKey("pacientes.id_PK"), nullable=False)
    doctor_origen_id_FK: Mapped[int] = mapped_column(ForeignKey("doctores.id_PK"), nullable=False)
    doctor_destino_id_FK: Mapped[int] = mapped_column(ForeignKey("doctores.id_PK"), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text)
    citas_reasignadas: Mapped[int] = mapped_column(Integer, default=0)
    realizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_PK"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    paciente = relationship("Paciente")
    doctor_origen = relationship("Doctor", foreign_keys=[doctor_origen_id_FK])
    doctor_destino = relationship("Doctor", foreign_keys=[doctor_destino_id_FK])
