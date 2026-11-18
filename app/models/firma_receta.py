from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.types import LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

# BLOB grande en MySQL (LONGBLOB); en otros motores, el binario normal
PDF_BINARIO = LargeBinary().with_variant(mysql.LONGBLOB(), "mysql")


class FirmaReceta(Base):
    """Firma electrónica SIMULADA de una receta (una por receta).

    Guarda el PDF original firmado y la firma separada (detached): RSASSA-PSS con
    SHA-256 sobre el manifiesto (`manifiesto_json`), que incluye el hash del PDF.
    """

    __tablename__ = "firmas_recetas"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Token no adivinable (128 bits) que va en el QR / URL pública
    codigo_verificacion: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Identificador legible (aparece en el PDF)
    identificador: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)

    receta_id_FK: Mapped[int] = mapped_column(ForeignKey("recetas.id_PK"), nullable=False, unique=True)
    identidad_id_FK: Mapped[int] = mapped_column(ForeignKey("identidades_firma_simulada.id_PK"), nullable=False)
    firmado_por_usuario_id_FK: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_PK"))

    fecha_firma: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC (sin zona)
    algoritmo_firma: Mapped[str] = mapped_column(String(50), nullable=False)

    hash_pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_contenido_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifiesto_json: Mapped[str] = mapped_column(Text, nullable=False)
    firma_b64: Mapped[str] = mapped_column(Text, nullable=False)

    pdf_original: Mapped[bytes] = mapped_column(PDF_BINARIO, nullable=False)
    tamano_pdf: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url_verificacion: Mapped[str] = mapped_column(String(500), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    receta = relationship("Receta")
    identidad = relationship("IdentidadFirmaSimulada")
