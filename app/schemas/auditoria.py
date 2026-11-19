from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CambioOut(BaseModel):
    campo: str
    etiqueta: str
    antes: str
    despues: str


class AuditoriaOut(BaseModel):
    # --- datos originales (se conservan por compatibilidad)
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
    # --- explicación en lenguaje sencillo
    usuario_nombre: Optional[str] = None
    usuario_rol: Optional[str] = None
    area: Optional[str] = None
    area_texto: Optional[str] = None
    tipo_accion: Optional[str] = None
    accion_texto: Optional[str] = None
    resumen: Optional[str] = None
    tono: Optional[str] = None
    icono: Optional[str] = None
    modo_cambios: Optional[str] = None
    cambios: list[CambioOut] = []
    model_config = ConfigDict(from_attributes=True)
