from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Consulta(Base):
    __tablename__ = "consultas"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    cita_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("citas.id_PK")
    )

    paciente_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("pacientes.id_PK")
    )

    doctor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("doctores.id_PK")
    )

    diagnostico: Mapped[str | None] = mapped_column(Text)
    tratamiento: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)

    fecha_visita: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    signos_vitales: Mapped[dict | None] = mapped_column(
        JSON
    )

    fecha_proxima_cita: Mapped[date | None] = mapped_column(
        Date
    )

    codigo_cie10: Mapped[str | None] = mapped_column(
        String(20)
    )

    cita = relationship("Cita")
    paciente = relationship("Paciente")
    doctor = relationship("Doctor")