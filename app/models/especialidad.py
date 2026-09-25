from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Especialidad(Base):
    __tablename__ = "especialidades"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text
    )

    codigo: Mapped[str | None] = mapped_column(
        String(50)
    )

    esta_activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )