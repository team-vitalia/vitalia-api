from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SalaBase(BaseModel):
    nombre: str = Field(..., max_length=150)
    tipo: Optional[str] = None
    ubicacion: Optional[str] = None
    estado: Optional[str] = "disponible"
    capacidad: Optional[int] = Field(None, gt=0)
    piso: Optional[str] = None
    lista_equipamiento: Optional[str] = None


class SalaCreate(SalaBase):
    pass


class SalaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    tipo: Optional[str] = None
    ubicacion: Optional[str] = None
    estado: Optional[str] = None
    capacidad: Optional[int] = Field(None, gt=0)
    piso: Optional[str] = None
    lista_equipamiento: Optional[str] = None


class SalaEstadoUpdate(BaseModel):
    estado: str = Field(..., pattern="^(disponible|ocupada|mantenimiento|inactiva)$")


class SalaOut(SalaBase):
    id_PK: int
    model_config = ConfigDict(from_attributes=True)
