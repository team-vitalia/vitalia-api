from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class AvisoSuperadmin(Base):
    __tablename__ = "avisos_superadmin"

    id_PK: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    clinica_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("clinicas.id_PK", ondelete="CASCADE"),
        nullable=True
    )

    titulo: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    mensaje: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    tipo: Mapped[str] = mapped_column(
        String(30),
        default="informativo",
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    fecha_expiracion: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    creado_por_usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK", ondelete="SET NULL"),
        nullable=True
    )

    clinica = relationship("Clinica", back_populates="avisos")
    creador = relationship("Usuario")
