from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Dispensacion(Base):
    """Medicamento entregado al paciente a partir de un ítem de receta."""

    __tablename__ = "dispensaciones"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    clinica_id_FK: Mapped[int | None] = mapped_column(ForeignKey("clinicas.id_PK"))
    receta_id_FK: Mapped[int] = mapped_column(ForeignKey("recetas.id_PK"), nullable=False)
    item_receta_id_FK: Mapped[int] = mapped_column(ForeignKey("items_receta.id_PK"), nullable=False)
    inventario_id_FK: Mapped[int] = mapped_column(ForeignKey("inventario.id_PK"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario_id_FK: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_PK"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notas: Mapped[str | None] = mapped_column(Text)

    receta = relationship("Receta")
    item = relationship("ItemReceta")
    lote = relationship("Inventario")
    usuario = relationship("Usuario")
