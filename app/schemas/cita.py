from datetime import date, time

from pydantic import BaseModel


class CitaCrear(BaseModel):
    paciente_id_FK: int
    doctor_id_FK: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado: str = "programada"
    motivo: str | None = None
    notas: str | None = None
    sala_id_FK: int | None = None
    requiere_equipo: bool = False
    equipo_id_FK: int | None = None
    accion_equipo: str | None = None


class CitaEstado(BaseModel):
    estado: str


class CitaReprogramar(BaseModel):
    fecha: date
    hora_inicio: time
    hora_fin: time
    motivo: str | None = None
    notas: str | None = None
    sala_id_FK: int | None = None
    requiere_equipo: bool | None = None
    equipo_id_FK: int | None = None
    accion_equipo: str | None = None


class CitaActualizar(BaseModel):
    fecha: date | None = None
    hora_inicio: time | None = None
    hora_fin: time | None = None
    estado: str | None = None
    motivo: str | None = None
    notas: str | None = None


class CitaResponse(BaseModel):
    id_PK: int
    paciente_id_FK: int | None
    doctor_id_FK: int | None
    fecha: date | None
    hora_inicio: time | None
    hora_fin: time | None
    estado: str | None
    motivo: str | None
    notas: str | None
    creado_por: int | None
    google_event_id: str | None = None
    sala_id_FK: int | None = None
    sala_nombre: str | None = None
    requiere_equipo: bool = False
    equipo_id_FK: int | None = None
    equipo_nombre: str | None = None
    accion_equipo: str | None = None
    no_realizada: bool = False

    class Config:
        from_attributes = True