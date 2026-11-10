from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoArticulo = Literal["medicamento", "insumo", "equipo"]


class MedicamentoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    principio_activo: str | None = None
    presentacion: str | None = None
    requiere_receta: bool | None = None
    descripcion: str | None = None
    codigo_barras: str | None = Field(default=None, max_length=100)
    categoria: str | None = Field(default=None, max_length=100)
    # Catálogo de almacén: medicamentos, insumos (guantes, jeringas...) y equipo
    tipo_articulo: TipoArticulo = "medicamento"
    unidad_medida: str | None = Field(default=None, max_length=30)
    stock_minimo: int = Field(default=0, ge=0)


class MedicamentoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    principio_activo: str | None = None
    presentacion: str | None = None
    requiere_receta: bool | None = None
    descripcion: str | None = None
    codigo_barras: str | None = Field(default=None, max_length=100)
    categoria: str | None = Field(default=None, max_length=100)
    tipo_articulo: TipoArticulo | None = None
    unidad_medida: str | None = Field(default=None, max_length=30)
    stock_minimo: int | None = Field(default=None, ge=0)


class MedicamentoResponse(BaseModel):
    id_PK: int
    nombre: str
    presentacion: str | None = None
    requiere_receta: bool | None = None
    principio_activo: str | None = None
    descripcion: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    tipo_articulo: str = "medicamento"
    unidad_medida: str | None = None
    stock_minimo: int = 0
    stock_actual: int = 0

    model_config = ConfigDict(from_attributes=True)
