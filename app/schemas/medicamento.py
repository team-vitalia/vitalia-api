from pydantic import BaseModel, ConfigDict, Field


class MedicamentoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    principio_activo: str | None = None
    presentacion: str | None = None
    requiere_receta: bool | None = None
    descripcion: str | None = None
    codigo_barras: str | None = Field(default=None, max_length=100)
    categoria: str | None = Field(default=None, max_length=100)


class MedicamentoResponse(BaseModel):
    id_PK: int
    nombre: str
    presentacion: str | None = None
    requiere_receta: bool | None = None
    stock_actual: int = 0

    model_config = ConfigDict(from_attributes=True)