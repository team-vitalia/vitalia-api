from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Alergia(Base):
    __tablename__ = "alergias"

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

    severidad: Mapped[str | None] = mapped_column(
        String(50)
    )

    tipo_alergia: Mapped[str | None] = mapped_column(
        String(50)
    )