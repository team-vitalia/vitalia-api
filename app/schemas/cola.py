from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Optional


class ColaCrear(BaseModel):
    """Datos que el frontend envía para registrar una llegada"""
    cita_id_FK: int
    prioridad: Optional[str] = "normal"


class ColaActualizar(BaseModel):
    """Datos para actualizar una cola (ej. llamar al paciente)"""
    estado: Optional[str] = None
    numero_consultorio: Optional[str] = None


class ColaResponse(BaseModel):
    """Datos que el backend devuelve al frontend"""
    id_PK: int
    cita_id_FK: int
    paciente_id_FK: Optional[int]
    doctor_id_FK: Optional[int]
    numero_cola: Optional[str] = None  # 👈 Puede ser None
    estado: Optional[str]
    hora_registro: Optional[datetime]
    prioridad: Optional[str]
    hora_llamado: Optional[datetime]
    numero_consultorio: Optional[str]

    @field_validator("numero_cola", mode="before")
    @classmethod
    def convertir_numero_cola(cls, valor):
        """Convierte cualquier valor a string"""
        if valor is None:
            return None
        return str(valor).zfill(3)  # Ej: 1 → "001"

    class Config:
        from_attributes = True