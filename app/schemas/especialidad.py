
from pydantic import BaseModel, ConfigDict, Field


class EspecialidadCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None
    codigo: str | None = None


class EspecialidadActualizar(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None
    codigo: str | None = None


class EspecialidadResponse(BaseModel):
    id_PK: int
    nombre: str
    descripcion: str | None
    codigo: str | None
    esta_activo: bool

    model_config = ConfigDict(from_attributes=True)