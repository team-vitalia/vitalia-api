from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.connection import Base


class CancelacionSuscripcion(Base):
    __tablename__ = "cancelaciones_suscripcion"

    id_PK: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    id = synonym("id_PK")

    clinica_id_FK: Mapped[int] = mapped_column(
        ForeignKey("clinicas.id_PK"),
        nullable=False
    )
    clinica_id = synonym("clinica_id_FK")

    plan_anterior_id_FK: Mapped[int] = mapped_column(
        ForeignKey("planes_suscripcion.id_PK"),
        nullable=False
    )
    plan_anterior_id = synonym("plan_anterior_id_FK")

    fecha_cancelacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    motivo_categoria: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    comentarios_adicionales: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    aplica_reembolso: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    estado_reembolso: Mapped[str] = mapped_column(
        String(50),
        default="NO_APLICA",
        nullable=False
    )

    paypal_refund_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    clinica = relationship("Clinica", back_populates="cancelaciones")
    plan_anterior = relationship("PlanSuscripcion")
