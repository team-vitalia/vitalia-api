from datetime import date

from pydantic import BaseModel, Field


class AntecedenteCrear(BaseModel):
    descripcion: str | None = None
    diagnostico: str | None = None
    estado: str | None = Field(default=None, max_length=50)
    fecha_diagnostico: date | None = None
    tratamiento: str | None = None
    tipo_sangre: str | None = Field(default=None, max_length=10)
    nombre_contacto_emergencia: str | None = Field(default=None, max_length=150)
    telefono_contacto_emergencia: str | None = Field(default=None, max_length=20)


class RegistroCrear(BaseModel):
    tipo_registro: str | None = Field(default=None, max_length=100)
    notas_generales: str = Field(min_length=1)
    url_adjunto: str | None = Field(default=None, max_length=255)


class AlergiaCatalogoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str | None = None
    severidad: str | None = Field(default=None, max_length=50)
    tipo_alergia: str | None = Field(default=None, max_length=50)


class AlergiaPacienteCrear(BaseModel):
    alergia_id_FK: int
    severidad: str | None = Field(default=None, max_length=50)
    fecha_diagnostico: date | None = None
    notas: str | None = None
