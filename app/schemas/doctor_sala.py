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
        # hora_fin < hora_inicio es válido: el turno cruza la medianoche (p. ej. 23:00 → 04:00)
        if self.hora_fin == self.hora_inicio:
            raise ValueError("La hora de fin no puede ser igual a la de inicio")
        return self


class AsignacionesSalas(BaseModel):
    asignaciones: list[AsignacionSala] = Field(default_factory=list)


class AsignacionSalaOut(AsignacionSala):
    id_PK: int
    sala_nombre: Optional[str] = None
    sala_tipo: Optional[str] = None
    sala_piso: Optional[str] = None
    sala_estado: Optional[str] = None


# ---------------------------------------------------------------------------
#  Calendario de uso de salas (arrastrar doctor <-> sala <-> horario)
# ---------------------------------------------------------------------------
class AsignacionNueva(BaseModel):
    """Un bloque del calendario: este doctor usa esta sala este día en este horario."""

    doctor_id: int
    sala_id: int
    dia_semana: Optional[int] = Field(None, ge=0, le=6)  # 0 = lunes; None = todos los días
    hora_inicio: time
    hora_fin: time
    notificar: bool = True  # avisar al doctor (notificación en la app)

    @model_validator(mode="after")
    def _horas(self):
        # hora_fin < hora_inicio es válido: el turno cruza la medianoche (p. ej. 23:00 → 04:00)
        if self.hora_fin == self.hora_inicio:
            raise ValueError("La hora de fin no puede ser igual a la de inicio")
        return self


class AsignacionCalendarioOut(BaseModel):
    id_PK: int
    doctor_id: int
    doctor_nombre: Optional[str] = None
    especialidad: Optional[str] = None
    sala_id: int
    sala_nombre: Optional[str] = None
    sala_tipo: Optional[str] = None
    sala_piso: Optional[str] = None
    sala_estado: Optional[str] = None
    dia_semana: Optional[int] = None
    hora_inicio: time
    hora_fin: time


class ConflictoOut(BaseModel):
    tipo: str  # doctor_ocupado | sala_ocupada | sala_no_disponible
    mensaje: str


class ValidacionAsignacionOut(BaseModel):
    valido: bool
    conflictos: list[ConflictoOut] = Field(default_factory=list)
