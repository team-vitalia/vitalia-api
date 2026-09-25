from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Cola(Base):
    __tablename__ = "colas"

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

    numero_cola: Mapped[int | None] = mapped_column(Integer)

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    hora_registro: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    prioridad: Mapped[str | None] = mapped_column(
        String(50)
    )

    hora_llamado: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    numero_consultorio: Mapped[str | None] = mapped_column(
        String(20)
    )

    cita = relationship("Cita")
    paciente = relationship("Paciente")
    doctor = relationship("Doctor")