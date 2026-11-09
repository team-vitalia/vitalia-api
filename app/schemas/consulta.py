from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsultaCrear(BaseModel):
    cita_id_FK: int
    diagnostico: str | None = None
    tratamiento: str | None = None
    notas: str | None = None
    signos_vitales: dict | None = None
    fecha_proxima_cita: date | None = None
    codigo_cie10: str | None = Field(default=None, max_length=20)
    # Marca la cita como «completada» al registrar la consulta
    finalizar_cita: bool = True


class ConsultaActualizar(BaseModel):
    diagnostico: str | None = None
    tratamiento: str | None = None
    notas: str | None = None
    signos_vitales: dict | None = None
    fecha_proxima_cita: date | None = None
    codigo_cie10: str | None = Field(default=None, max_length=20)


class ConsultaOut(BaseModel):
    id_PK: int
    cita_id_FK: int | None = None
    paciente_id_FK: int | None = None
    doctor_id_FK: int | None = None
    diagnostico: str | None = None
    tratamiento: str | None = None
    notas: str | None = None
    fecha_visita: datetime | None = None
    signos_vitales: dict | None = None
    fecha_proxima_cita: date | None = None
    codigo_cie10: str | None = None
    receta_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)
