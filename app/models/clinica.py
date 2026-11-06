"""Modelo Clinica actualizado con columna paypal_subscription_id para asociar la suscripcion de PayPal."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class Clinica(Base):
    __tablename__ = "clinicas"

    id_PK: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre_comercial: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    plan_id_FK: Mapped[int] = mapped_column(
        ForeignKey("planes_suscripcion.id_PK"),
        nullable=False
    )
    plan_id = synonym("plan_id_FK")

    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    activa: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    paypal_subscription_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True
    )

    plan = relationship(
        "PlanSuscripcion",
        back_populates="clinicas"
    )

    usuarios = relationship(
        "Usuario",
        back_populates="clinica"
    )

    pacientes = relationship(
        "Paciente",
        back_populates="clinica"
    )

    citas = relationship(
        "Cita",
        back_populates="clinica"
    )

    salas = relationship(
        "Sala",
        back_populates="clinica"
    )

    medicamentos = relationship(
        "Medicamento",
        back_populates="clinica"
    )
