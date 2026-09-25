from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Receta(Base):
    __tablename__ = "recetas"

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

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    consulta_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("consultas.id_PK")
    )

    codigo_qr: Mapped[str | None] = mapped_column(
        String(255)
    )

    hash_firma: Mapped[str | None] = mapped_column(
        String(255)
    )

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")
    consulta = relationship("Consulta")