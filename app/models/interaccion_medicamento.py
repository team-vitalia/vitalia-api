from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class InteraccionMedicamento(Base):
    __tablename__ = "interacciones_medicamentos"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    medicamento_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("medicamentos.id_PK")
    )

    medicamento_interactuante_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("medicamentos.id_PK")
    )

    severidad: Mapped[str | None] = mapped_column(
        String(50)
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text
    )

    nivel_evidencia: Mapped[str | None] = mapped_column(
        String(100)
    )

    accion_requerida: Mapped[str | None] = mapped_column(
        String(200)
    )

    medicamento = relationship(
        "Medicamento",
        foreign_keys=[medicamento_id_FK]
    )

    medicamento_interactuante = relationship(
        "Medicamento",
        foreign_keys=[medicamento_interactuante_id_FK]
    )