from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ESTADOS_SALA = ("disponible", "ocupada", "mantenimiento", "inactiva")


def _estado_valido(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in ESTADOS_SALA:
        raise ValueError(f"Estado no válido. Opciones: {', '.join(ESTADOS_SALA)}")
    return v


def _limpiar(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    return v or None


class SalaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    tipo: Optional[str] = Field(None, max_length=100)
    ubicacion: Optional[str] = Field(None, max_length=200)
    estado: Optional[str] = "disponible"
    capacidad: Optional[int] = Field(None, gt=0, le=500)
    piso: Optional[str] = Field(None, max_length=20)
    lista_equipamiento: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre de la sala es obligatorio")
        return v

    @field_validator("tipo", "ubicacion", "piso", "lista_equipamiento")
    @classmethod
    def _textos(cls, v):
        return _limpiar(v)

    @field_validator("estado")
    @classmethod
    def _estado(cls, v):
        return _estado_valido(v)


class SalaCreate(SalaBase):
    pass


class SalaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=150)
    tipo: Optional[str] = Field(None, max_length=100)
    ubicacion: Optional[str] = Field(None, max_length=200)
    estado: Optional[str] = None
    capacidad: Optional[int] = Field(None, gt=0, le=500)
    piso: Optional[str] = Field(None, max_length=20)
    lista_equipamiento: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("El nombre de la sala no puede quedar vacío")
        return v

    @field_validator("tipo", "ubicacion", "piso", "lista_equipamiento")
    @classmethod
    def _textos(cls, v):
        return _limpiar(v)

    @field_validator("estado")
    @classmethod
    def _estado(cls, v):
        return _estado_valido(v)


class SalaEstadoUpdate(BaseModel):
    estado: str = Field(..., pattern="^(disponible|ocupada|mantenimiento|inactiva)$")


class SalaOut(SalaBase):
    id_PK: int
    # Datos calculados para las tarjetas de la app
    total_equipos: int = 0
    equipos_con_problema: int = 0
    citas_proximas: int = 0
    model_config = ConfigDict(from_attributes=True)
