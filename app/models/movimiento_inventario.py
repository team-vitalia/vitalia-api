from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    inventario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("inventario.id_PK")
    )

    cantidad: Mapped[int | None] = mapped_column(
        Integer
    )

    tipo_movimiento_FK: Mapped[int | None] = mapped_column(
        ForeignKey("tipos_movimiento_inventario.id_PK")
    )

    usuario_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK")
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    id_referencia: Mapped[int | None] = mapped_column(
        Integer
    )

    stock_anterior: Mapped[int | None] = mapped_column(
        Integer
    )

    stock_nuevo: Mapped[int | None] = mapped_column(
        Integer
    )

    inventario = relationship("Inventario")
    tipo_movimiento = relationship("TipoMovimientoInventario")
    usuario = relationship("Usuario")