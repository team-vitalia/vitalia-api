from datetime import date

from pydantic import BaseModel, EmailStr


class PacienteCrear(BaseModel):
    nombre: str
    apellido: str
    fecha_nacimiento: date | None = None
    genero: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    correo_electronico: EmailStr | None = None


class PacienteResponse(BaseModel):
    id_PK: int
    nombre: str
    apellido: str
    fecha_nacimiento: date | None
    genero: str | None
    telefono: str | None
    direccion: str | None
    correo_electronico: EmailStr | None
    estado: str | None

    class Config:
        from_attributes = True