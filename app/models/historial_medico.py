from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class HistorialMedico(Base):
    __tablename__ = "historial_medico"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    paciente_id_FK: Mapped[int] = mapped_column(
        ForeignKey("pacientes.id_PK"),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(Text)
    diagnostico: Mapped[str | None] = mapped_column(Text)

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    fecha_diagnostico: Mapped[date | None] = mapped_column(Date)

    tratamiento: Mapped[str | None] = mapped_column(Text)

    doctor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("doctores.id_PK")
    )

    tipo_sangre: Mapped[str | None] = mapped_column(
        String(10)
    )

    nombre_contacto_emergencia: Mapped[str | None] = mapped_column(
        String(150)
    )

    telefono_contacto_emergencia: Mapped[str | None] = mapped_column(
        String(20)
    )

    proveedor_seguro_id_FK: Mapped[int | None] = mapped_column(
        nullable=True
    )

    numero_poliza_seguro: Mapped[str | None] = mapped_column(
        String(100)
    )

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")