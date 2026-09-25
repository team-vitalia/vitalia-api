from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Role(Base):
    __tablename__ = "roles"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    esta_activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )