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


class NotificacionOut(BaseModel):
    id_PK: int
    usuario_id_FK: int | None = None
    mensaje: str | None = None
    estado: str | None = None
    creado_en: datetime
    tipo: str | None = None
    enlace: str | None = None
    leido_en: datetime | None = None

    class Config:
        from_attributes = True
