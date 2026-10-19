from datetime import time
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AsignacionSala(BaseModel):
    sala_id_FK: int
    dia_semana: Optional[int] = Field(None, ge=0, le=6)  # 0 = lunes; None = todos
    hora_inicio: time
    hora_fin: time

    @model_validator(mode="after")
    def _horas(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio")
        return self


class AsignacionesSalas(BaseModel):
    asignaciones: list[AsignacionSala] = Field(default_factory=list)


class AsignacionSalaOut(AsignacionSala):
    id_PK: int
    sala_nombre: Optional[str] = None
    sala_tipo: Optional[str] = None
    sala_piso: Optional[str] = None
    sala_estado: Optional[str] = None
