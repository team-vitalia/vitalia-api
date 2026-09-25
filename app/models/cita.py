from datetime import date, time

from sqlalchemy import Date, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Cita(Base):
    __tablename__ = "citas"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    paciente_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("pacientes.id_PK")
    )

    doctor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("doctores.id_PK")
    )

    fecha: Mapped[date | None] = mapped_column(Date)

    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fin: Mapped[time | None] = mapped_column(Time)

    evento_calendario_id: Mapped[int | None] = mapped_column(
        ForeignKey("eventos_calendario.id_PK")
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    motivo: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)

    creado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK")
    )

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")
    evento_calendario = relationship("EventoCalendario")
    usuario_creador = relationship("Usuario")