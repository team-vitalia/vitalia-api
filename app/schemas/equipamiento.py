from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EquipamientoBase(BaseModel):
    nombre_equipo: Optional[str] = Field(None, max_length=200)
    numero_serie: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = "operativo"
    fecha_compra: Optional[date] = None
    ultimo_mantenimiento: Optional[date] = None
    proximo_mantenimiento: Optional[date] = None


class EquipamientoCreate(EquipamientoBase):
    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_compra and self.fecha_compra > date.today():
            raise ValueError("fecha_compra no puede ser futura")
        if (
            self.ultimo_mantenimiento
            and self.proximo_mantenimiento
            and self.proximo_mantenimiento < self.ultimo_mantenimiento
        ):
            raise ValueError(
                "proximo_mantenimiento no puede ser anterior a ultimo_mantenimiento"
            )
        return self


class EquipamientoUpdate(BaseModel):
    nombre_equipo: Optional[str] = None
    numero_serie: Optional[str] = None
    estado: Optional[str] = None
    fecha_compra: Optional[date] = None
    ultimo_mantenimiento: Optional[date] = None
    proximo_mantenimiento: Optional[date] = None


class EquipamientoOut(EquipamientoBase):
    id_PK: int
    sala_id_FK: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
