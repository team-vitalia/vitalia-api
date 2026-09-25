from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK")
    )

    mensaje: Mapped[str | None] = mapped_column(
        Text
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    tipo: Mapped[str | None] = mapped_column(
        String(50)
    )

    enlace: Mapped[str | None] = mapped_column(
        String(255)
    )

    leido_en: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    usuario = relationship("Usuario")