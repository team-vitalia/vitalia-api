
from pydantic import BaseModel, ConfigDict, Field


class RoleCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = None


class RoleActualizar(BaseModel):
    nombre: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )
    descripcion: str | None = None
    esta_activo: bool | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_PK: int
    nombre: str
    descripcion: str | None = None
    esta_activo: bool