from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIPOS_EQUIPO = (
    "diagnostico",
    "monitoreo",
    "cirugia",
    "soporte_vital",
    "laboratorio",
    "esterilizacion",
    "mobiliario",
    "otro",
)
ESTADOS_EQUIPO = ("operativo", "mantenimiento", "fuera_de_servicio")


def _validar_catalogo(valor: Optional[str], permitidos: tuple[str, ...], campo: str) -> Optional[str]:
    if valor is None:
        return valor
    if valor not in permitidos:
        raise ValueError(f"{campo} no válido. Opciones: {', '.join(permitidos)}")
    return valor


def validar_fechas_equipo(
    fecha_compra: Optional[date],
    ultimo: Optional[date],
    proximo: Optional[date],
) -> None:
    """Reglas de fechas compartidas por crear y actualizar."""
    if fecha_compra and fecha_compra > date.today():
        raise ValueError("La fecha de compra no puede ser futura")
    if ultimo and ultimo > date.today():
        raise ValueError("El último mantenimiento no puede ser una fecha futura")
    if ultimo and proximo and proximo < ultimo:
        raise ValueError("El próximo mantenimiento no puede ser anterior al último")
    if fecha_compra and ultimo and ultimo < fecha_compra:
        raise ValueError("El último mantenimiento no puede ser anterior a la compra")


class EquipamientoBase(BaseModel):
    nombre_equipo: Optional[str] = Field(None, max_length=200)
    tipo_equipo: Optional[str] = "otro"
    numero_serie: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = "operativo"
    fecha_compra: Optional[date] = None
    ultimo_mantenimiento: Optional[date] = None
    proximo_mantenimiento: Optional[date] = None

    @field_validator("tipo_equipo")
    @classmethod
    def _tipo(cls, v):
        return _validar_catalogo(v, TIPOS_EQUIPO, "tipo_equipo")

    @field_validator("estado")
    @classmethod
    def _estado(cls, v):
        return _validar_catalogo(v, ESTADOS_EQUIPO, "estado")


class EquipamientoCreate(EquipamientoBase):
    @model_validator(mode="after")
    def validar_fechas(self):
        validar_fechas_equipo(self.fecha_compra, self.ultimo_mantenimiento, self.proximo_mantenimiento)
        return self


class EquipamientoUpdate(BaseModel):
    nombre_equipo: Optional[str] = Field(None, max_length=200)
    tipo_equipo: Optional[str] = None
    numero_serie: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = None
    fecha_compra: Optional[date] = None
    ultimo_mantenimiento: Optional[date] = None
    proximo_mantenimiento: Optional[date] = None

    @field_validator("tipo_equipo")
    @classmethod
    def _tipo(cls, v):
        return _validar_catalogo(v, TIPOS_EQUIPO, "tipo_equipo")

    @field_validator("estado")
    @classmethod
    def _estado(cls, v):
        return _validar_catalogo(v, ESTADOS_EQUIPO, "estado")


class EquipamientoOut(EquipamientoBase):
    id_PK: int
    sala_id_FK: Optional[int] = None
    # Calculado: "al_dia", "proximo" (vence en <= 30 días), "vencido" o "sin_programar"
    mantenimiento_estado: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
