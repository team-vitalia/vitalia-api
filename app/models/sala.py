from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Sala(Base):
    __tablename__ = "salas"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    tipo: Mapped[str | None] = mapped_column(
        String(100)
    )

    ubicacion: Mapped[str | None] = mapped_column(
        String(200)
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    capacidad: Mapped[int | None] = mapped_column(
        Integer
    )

    piso: Mapped[str | None] = mapped_column(
        String(20)
    )

    lista_equipamiento: Mapped[str | None] = mapped_column(
        Text
    )