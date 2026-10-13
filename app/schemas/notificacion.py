from datetime import datetime
from pydantic import BaseModel


class NotificacionResponse(BaseModel):
    id_PK: int
    usuario_id_FK: int | None
    mensaje: str | None
    tipo: str | None
    estado: str | None
    creado_en: datetime | None
    enlace: str | None
    leido_en: datetime | None

    class Config:
        from_attributes = True


class NotificacionesLote(BaseModel):
    ids: list[int]
