from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class EventoCalendario(Base):
    __tablename__ = "eventos_calendario"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    titulo: Mapped[str | None] = mapped_column(
        String(200)
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text
    )

    fecha_inicio: Mapped[object | None] = mapped_column(
        DateTime
    )

    fecha_fin: Mapped[object | None] = mapped_column(
        DateTime
    )

    todo_el_dia: Mapped[bool | None] = mapped_column(
        Boolean
    )

    ubicacion: Mapped[str | None] = mapped_column(
        String(200)
    )

    tipo_evento: Mapped[str | None] = mapped_column(
        String(100)
    )