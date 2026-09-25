from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    apellido: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)

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