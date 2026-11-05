from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    clinica_id_FK: Mapped[int] = mapped_column(
        ForeignKey("clinicas.id_PK"),
        nullable=False
    )
    clinica_id = synonym("clinica_id_FK")

    nombre: Mapped[str] = mapped_column(
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

    correo_electronico: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False
    )

    hash_contrasena: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    rol_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("roles.id_PK")
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
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

    ultimo_acceso: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20)
    )

    intentos_fallidos: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    token_restablecimiento: Mapped[str | None] = mapped_column(
        String(255)
    )

    rol = relationship("Role")
    clinica = relationship("Clinica", back_populates="usuarios")
