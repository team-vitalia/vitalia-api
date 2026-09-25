from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Proveedor(Base):
    __tablename__ = "proveedores"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20)
    )

    correo_electronico: Mapped[str | None] = mapped_column(
        String(150)
    )

    direccion: Mapped[str | None] = mapped_column(
        Text
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )