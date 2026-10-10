from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.doctor_especialidad import DoctorEspecialidad
from app.database.connection import Base


class Doctor(Base):
    __tablename__ = "doctores"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK"),
        unique=True
    )

    especialidad_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("especialidades.id_PK")
    )

    numero_licencia: Mapped[str | None] = mapped_column(
        String(50)
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    costo_consulta: Mapped[float | None] = mapped_column(
        Numeric(10, 2)
    )

    ruta_firma: Mapped[str | None] = mapped_column(
        String(255)
    )
    
    especialidades_asignadas = relationship(
        "DoctorEspecialidad",
        back_populates="doctor",
        cascade="all, delete-orphan"
    )

    usuario = relationship("Usuario")
    especialidad = relationship("Especialidad")