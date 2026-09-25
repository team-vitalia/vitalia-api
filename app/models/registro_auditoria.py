from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class RegistroAuditoria(Base):
    __tablename__ = "registros_auditoria"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK")
    )

    accion: Mapped[str | None] = mapped_column(
        String(100)
    )

    id_registro: Mapped[int | None] = mapped_column(
        Integer
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text
    )

    marca_tiempo: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    nombre_tabla: Mapped[str | None] = mapped_column(
        String(100)
    )

    valores_antiguos: Mapped[dict | None] = mapped_column(
        JSON
    )

    valores_nuevos: Mapped[dict | None] = mapped_column(
        JSON
    )

    direccion_ip: Mapped[str | None] = mapped_column(
        String(45)
    )

    usuario = relationship("Usuario")