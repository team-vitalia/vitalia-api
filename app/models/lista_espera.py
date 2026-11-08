from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class ListaEspera(Base):
    """Pacientes que esperan disponibilidad de una cita (waitlists)."""

    __tablename__ = "lista_espera"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    clinica_id_FK: Mapped[int] = mapped_column(ForeignKey("clinicas.id_PK"), nullable=False)
    paciente_id_FK: Mapped[int] = mapped_column(ForeignKey("pacientes.id_PK"), nullable=False)
    doctor_id_FK: Mapped[int | None] = mapped_column(ForeignKey("doctores.id_PK"))
    especialidad_id_FK: Mapped[int | None] = mapped_column(ForeignKey("especialidades.id_PK"))

    fecha_deseada: Mapped[date | None] = mapped_column(Date)
    motivo: Mapped[str | None] = mapped_column(Text)
    # normal | alta | urgente
    prioridad: Mapped[str] = mapped_column(String(20), default="normal")
    # en_espera | notificado | asignada | cancelada
    estado: Mapped[str] = mapped_column(String(30), default="en_espera")

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    atendida_en: Mapped[datetime | None] = mapped_column(DateTime)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_PK"))
    cita_id_FK: Mapped[int | None] = mapped_column(ForeignKey("citas.id_PK"))

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")
    especialidad = relationship("Especialidad")
