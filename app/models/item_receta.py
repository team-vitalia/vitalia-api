from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class ItemReceta(Base):
    __tablename__ = "items_receta"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    receta_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("recetas.id_PK")
    )

    medicamento_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("medicamentos.id_PK")
    )

    dosis: Mapped[str | None] = mapped_column(
        String(100)
    )

    frecuencia: Mapped[str | None] = mapped_column(
        String(100)
    )

    duracion: Mapped[str | None] = mapped_column(
        String(100)
    )

    cantidad: Mapped[int | None] = mapped_column(
        Integer
    )

    instrucciones: Mapped[str | None] = mapped_column(
        Text
    )

    via_administracion: Mapped[str | None] = mapped_column(
        String(100)
    )

    recargas_permitidas: Mapped[int | None] = mapped_column(
        Integer
    )

    receta = relationship("Receta")
    medicamento = relationship("Medicamento")