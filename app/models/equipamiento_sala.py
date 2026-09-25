from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class EquipamientoSala(Base):
    __tablename__ = "equipamiento_sala"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    sala_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("salas.id_PK")
    )

    nombre_equipo: Mapped[str | None] = mapped_column(
        String(200)
    )

    numero_serie: Mapped[str | None] = mapped_column(
        String(100)
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    fecha_compra: Mapped[date | None] = mapped_column(Date)

    ultimo_mantenimiento: Mapped[date | None] = mapped_column(Date)

    proximo_mantenimiento: Mapped[date | None] = mapped_column(Date)

    sala = relationship("Sala")