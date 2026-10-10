
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class DoctorEspecialidad(Base):
    __tablename__ = "doctor_especialidades"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    doctor_id_FK: Mapped[int] = mapped_column(
        ForeignKey("doctores.id_PK"),
        nullable=False
    )

    especialidad_id_FK: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id_PK"),
        nullable=False
    )

    doctor = relationship(
        "Doctor",
        back_populates="especialidades_asignadas"
    )

    especialidad = relationship("Especialidad")