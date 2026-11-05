from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class Sala(Base):
    __tablename__ = "salas"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    clinica_id_FK: Mapped[int] = mapped_column(
        ForeignKey("clinicas.id_PK"),
        nullable=False
    )
    clinica_id = synonym("clinica_id_FK")

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

    clinica = relationship("Clinica", back_populates="salas")
