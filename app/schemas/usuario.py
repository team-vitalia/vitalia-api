
from datetime import date

from pydantic import BaseModel, EmailStr, Field


class UsuarioCrear(BaseModel):
    # Datos generales del usuario
    nombre: str
    correo_electronico: EmailStr
    password: str
    rol_id_FK: int

    # Datos de paciente
    apellido: str | None = None
    fecha_nacimiento: date | None = None
    genero: str | None = None
    telefono: str | None = None
    direccion: str | None = None

    # Datos de doctor
    especialidad_id_FK: int | None = None  # Compatibilidad
    especialidad_ids: list[int] = Field(default_factory=list)
    numero_licencia: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)


class UsuarioResponse(BaseModel):
    id_PK: int
    nombre: str
    correo_electronico: EmailStr
    rol_id_FK: int | None
    estado: str | None

    class Config:
        from_attributes = True


class UsuarioActualizar(BaseModel):
    nombre: str | None = None
    correo_electronico: EmailStr | None = None
    telefono: str | None = None
    rol_id_FK: int | None = None
    estado: str | None = None