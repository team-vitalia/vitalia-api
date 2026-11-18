from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class IdentidadFirmaSimulada(Base):
    """Identidad y par de llaves RSA FICTICIOS de un médico de prueba.

    SIMULACIÓN ACADÉMICA: no es una e.firma ni un certificado real. La llave
    privada se guarda CIFRADA (PKCS#8 + frase) y nunca sale del backend.
    """

    __tablename__ = "identidades_firma_simulada"

    id_PK: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    clinica_id_FK: Mapped[int | None] = mapped_column(ForeignKey("clinicas.id_PK"))
    usuario_id_FK: Mapped[int] = mapped_column(ForeignKey("usuarios.id_PK"), nullable=False, unique=True)

    nombre_ficticio: Mapped[str] = mapped_column(String(150), nullable=False)
    cedula_ficticia: Mapped[str] = mapped_column(String(30), nullable=False)
    especialidad_ficticia: Mapped[str | None] = mapped_column(String(100))

    algoritmo: Mapped[str] = mapped_column(String(40), nullable=False, default="RSA-2048")
    clave_publica_pem: Mapped[str] = mapped_column(Text, nullable=False)
    huella_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    clave_privada_cifrada: Mapped[str] = mapped_column(Text, nullable=False)

    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    usuario = relationship("Usuario")
