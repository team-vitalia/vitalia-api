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

    class Config:
        from_attributes = True