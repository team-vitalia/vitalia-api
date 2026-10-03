from pydantic import BaseModel


class EspecialidadCrear(BaseModel):
    nombre: str
    descripcion: str | None = None
    codigo: str | None = None


class EspecialidadResponse(BaseModel):
    id_PK: int
    nombre: str
    descripcion: str | None
    codigo: str | None
    esta_activo: bool

    class Config:
        from_attributes = True