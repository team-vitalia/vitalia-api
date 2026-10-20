from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ItemRecetaCrear(BaseModel):
    medicamento_id_FK: int
    dosis: str
    frecuencia: str
    duracion: str
    cantidad: int
    instrucciones: str | None = None
    via_administracion: str | None = None
    recargas_permitidas: int | None = 0

class RecetaCrear(BaseModel):
    paciente_id_FK: int
    consulta_id_FK: int
    items: list[ItemRecetaCrear]

class RecetaResponse(BaseModel):
    id_PK: int
    paciente_id_FK: int | None
    doctor_id_FK: int | None
    consulta_id_FK: int | None
    estado: str | None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)