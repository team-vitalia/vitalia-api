from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class HistorialFirmaReceta(Base):
    """Bitácora de cada evento de una firma: FIRMADA, PDF_DESCARGADO, VERIFICACION."""

    __tablename__ = "historial_firmas_recetas"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    firma_id_FK: Mapped[int] = mapped_column(ForeignKey("firmas_recetas.id_PK"), nullable=False)
    receta_id_FK: Mapped[int] = mapped_column(ForeignKey("recetas.id_PK"), nullable=False)

    accion: Mapped[str] = mapped_column(String(30), nullable=False)
    # VALIDA | INVALIDA (solo en verificaciones)
    resultado: Mapped[str | None] = mapped_column(String(20))
    detalle: Mapped[str | None] = mapped_column(Text)

    usuario_id_FK: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_PK"))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
