from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class PlanSuscripcion(Base):
    __tablename__ = "planes_suscripcion"

    id_PK: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    precio_mensual: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    precio_anual: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    limite_personal: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    limite_pacientes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    limite_pacientes_mes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None
    )

    incluye_calendar: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    incluye_correos: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    limite_ia_mensual: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    incluye_contratos: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    incluye_salas: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    incluye_almacen: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    incluye_reportes: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    incluye_auditoria: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    incluye_roles: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    limite_sucursales: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )

    paypal_plan_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True
    )

    clinicas = relationship(
        "Clinica",
        back_populates="plan"
    )
