from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class PresentacionMedicamento(Base):
    """Concentración y forma farmacéutica de un medicamento (medication_presentations)."""

    __tablename__ = "presentaciones_medicamento"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    medicamento_id_FK: Mapped[int] = mapped_column(
        ForeignKey("medicamentos.id_PK"), nullable=False
    )

    concentracion: Mapped[str | None] = mapped_column(String(100))
    forma_farmaceutica: Mapped[str | None] = mapped_column(String(100))
    contenido: Mapped[str | None] = mapped_column(String(100))
    esta_activo: Mapped[bool] = mapped_column(Boolean, default=True)

    medicamento = relationship("Medicamento")
