from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    clinica_id_FK: Mapped[int] = mapped_column(
        ForeignKey("clinicas.id_PK"),
        nullable=False
    )
    clinica_id = synonym("clinica_id_FK")

    usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK"),
        unique=True,
        nullable=True
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    apellido: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    apellido_paterno: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    apellido_materno: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    curp: Mapped[str | None] = mapped_column(
        String(18),
        unique=True,
        nullable=True
    )

    fecha_nacimiento: Mapped[date | None] = mapped_column(
        Date
    )

    genero: Mapped[str | None] = mapped_column(
        String(20)
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20)
    )

    direccion: Mapped[str | None] = mapped_column(
        Text
    )

    correo_electronico: Mapped[str | None] = mapped_column(
        String(150)
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    usuario = relationship("Usuario")
    clinica = relationship("Clinica", back_populates="pacientes")
