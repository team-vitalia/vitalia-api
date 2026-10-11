from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContratoCrear(BaseModel):
    doctor_id_FK: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date | None = None
    estado: str = Field(min_length=1, max_length=50)
    tipo_contrato: str = Field(min_length=1, max_length=50)
    salario: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2
    )
    url_documento: str | None = Field(
        default=None,
        max_length=255
    )

    @model_validator(mode="after")
    def validar_fechas(self):
        if (
            self.fecha_fin is not None
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValueError(
                "La fecha de fin no puede ser anterior a la fecha de inicio"
            )
        return self

    @model_validator(mode="after")
    def validar_textos(self):
        if not self.estado.strip():
            raise ValueError("El estado es obligatorio")

        if not self.tipo_contrato.strip():
            raise ValueError("El tipo de contrato es obligatorio")

        return self


class ContratoActualizar(BaseModel):
    fecha_inicio: date | None = None
    fecha_fin: date | None = None

    estado: str | None = Field(
        default=None,
        min_length=1,
        max_length=50
    )

    tipo_contrato: str | None = Field(
        default=None,
        min_length=1,
        max_length=50
    )

    salario: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2
    )

    url_documento: str | None = Field(
        default=None,
        max_length=255
    )

    @model_validator(mode="after")
    def validar_textos(self):
        if self.estado is not None and not self.estado.strip():
            raise ValueError("El estado no puede estar vacío")

        if (
            self.tipo_contrato is not None
            and not self.tipo_contrato.strip()
        ):
            raise ValueError("El tipo de contrato no puede estar vacío")

        return self


class ContratoResponse(BaseModel):
    id_PK: int
    doctor_id_FK: int
    fecha_inicio: date | None
    fecha_fin: date | None
    estado: str | None
    tipo_contrato: str | None
    salario: Decimal | None
    url_documento: str | None

    model_config = ConfigDict(from_attributes=True)