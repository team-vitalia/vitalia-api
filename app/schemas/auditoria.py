from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditoriaOut(BaseModel):
    id_PK: int
    usuario_id_FK: Optional[int] = None
    accion: Optional[str] = None
    id_registro: Optional[int] = None
    descripcion: Optional[str] = None
    marca_tiempo: datetime
    nombre_tabla: Optional[str] = None
    valores_antiguos: Optional[dict[str, Any]] = None
    valores_nuevos: Optional[dict[str, Any]] = None
    direccion_ip: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
