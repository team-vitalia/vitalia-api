from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class Medicamento(Base):
    __tablename__ = "medicamentos"

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
        String(200),
        nullable=False
    )

    principio_activo: Mapped[str | None] = mapped_column(
        String(200)
    )

    presentacion: Mapped[str | None] = mapped_column(
        String(100)
    )

    requiere_receta: Mapped[bool | None] = mapped_column(
        Boolean
    )

    descripcion: Mapped[str | None] = mapped_column(Text)

    codigo_barras: Mapped[str | None] = mapped_column(
        String(100)
    )

    categoria: Mapped[str | None] = mapped_column(
        String(100)
    )

    clinica = relationship("Clinica", back_populates="medicamentos")
