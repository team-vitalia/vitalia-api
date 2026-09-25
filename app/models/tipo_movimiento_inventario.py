from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class TipoMovimientoInventario(Base):
    __tablename__ = "tipos_movimiento_inventario"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text
    )

    esta_activo: Mapped[bool] = mapped_column(
        default=True
    )