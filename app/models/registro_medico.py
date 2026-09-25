from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class RegistroMedico(Base):
    __tablename__ = "registros_medicos"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    paciente_id_FK: Mapped[int] = mapped_column(
        ForeignKey("pacientes.id_PK"),
        nullable=False
    )

    tipo_registro: Mapped[str | None] = mapped_column(
        String(100)
    )

    notas_generales: Mapped[str | None] = mapped_column(
        Text
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    doctor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("doctores.id_PK")
    )

    url_adjunto: Mapped[str | None] = mapped_column(
        String(255)
    )

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")