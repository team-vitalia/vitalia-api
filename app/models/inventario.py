from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Inventario(Base):
    __tablename__ = "inventario"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    medicamento_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("medicamentos.id_PK")
    )

    numero_lote: Mapped[str | None] = mapped_column(
        String(100)
    )

    stock_actual: Mapped[int | None] = mapped_column(
        Integer
    )

    ubicacion: Mapped[str | None] = mapped_column(
        String(150)
    )

    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date
    )

    precio_venta: Mapped[float | None] = mapped_column(
        Numeric(10, 2)
    )

    proveedor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id_PK")
    )

    fecha_recepcion: Mapped[date | None] = mapped_column(
        Date
    )

    medicamento = relationship("Medicamento")
    proveedor = relationship("Proveedor")