from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class ContratoDoctor(Base):
    __tablename__ = "contratos_doctor"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    doctor_id_FK: Mapped[int] = mapped_column(
        ForeignKey("doctores.id_PK"),
        nullable=False
    )

    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    tipo_contrato: Mapped[str | None] = mapped_column(
        String(50)
    )

    salario: Mapped[float | None] = mapped_column(
        Numeric(10, 2)
    )

    url_documento: Mapped[str | None] = mapped_column(
        String(255)
    )

    doctor = relationship("Doctor")