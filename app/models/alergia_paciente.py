from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class AlergiaPaciente(Base):
    __tablename__ = "alergias_paciente"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    paciente_id_FK: Mapped[int] = mapped_column(
        ForeignKey("pacientes.id_PK"),
        nullable=False
    )

    alergia_id_FK: Mapped[int] = mapped_column(
        ForeignKey("alergias.id_PK"),
        nullable=False
    )

    severidad: Mapped[str | None] = mapped_column(
        String(50)
    )

    fecha_diagnostico: Mapped[date | None] = mapped_column(
        Date
    )

    notas: Mapped[str | None] = mapped_column(
        Text
    )

    paciente = relationship("Paciente")
    alergia = relationship("Alergia")