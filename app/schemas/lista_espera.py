from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Prioridad = Literal["normal", "alta", "urgente"]
EstadoEspera = Literal["en_espera", "notificado", "asignada", "cancelada"]


class EsperaCrear(BaseModel):
    paciente_id_FK: int
    doctor_id_FK: int | None = None
    especialidad_id_FK: int | None = None
    fecha_deseada: date | None = None
    motivo: str | None = None
    prioridad: Prioridad = "normal"


class EsperaEstado(BaseModel):
    estado: EstadoEspera
    # Obligatorio cuando el estado es «asignada»
    cita_id_FK: int | None = None


class EsperaOut(BaseModel):
    id_PK: int
    paciente_id_FK: int
    paciente: str | None = None
    doctor_id_FK: int | None = None
    doctor: str | None = None
    especialidad_id_FK: int | None = None
    especialidad: str | None = None
    fecha_deseada: date | None = None
    motivo: str | None = None
    prioridad: str
    estado: str
    posicion: int | None = None
    creado_en: datetime
    atendida_en: datetime | None = None
    cita_id_FK: int | None = None

    model_config = ConfigDict(from_attributes=True)
