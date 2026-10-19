from datetime import time

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class DoctorSala(Base):
    """Sala asignada a un doctor con su horario de uso.

    dia_semana: 0 = lunes ... 6 = domingo. NULL = todos los días.
    """

    __tablename__ = "doctor_salas"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    doctor_id_FK: Mapped[int] = mapped_column(
        ForeignKey("doctores.id_PK"), nullable=False
    )
    sala_id_FK: Mapped[int] = mapped_column(
        ForeignKey("salas.id_PK"), nullable=False
    )

    dia_semana: Mapped[int | None] = mapped_column(Integer)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fin: Mapped[time | None] = mapped_column(Time)

    sala = relationship("Sala")
