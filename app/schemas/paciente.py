from datetime import date

from pydantic import BaseModel, EmailStr, field_validator

from app.core.validaciones import validar_curp, validar_nombre_persona


class PacienteCrear(BaseModel):
    nombre: str
    apellido: str
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    curp: str | None = None
    fecha_nacimiento: date | None = None
    genero: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    correo_electronico: EmailStr | None = None


    @field_validator("apellido_paterno", "apellido_materno")
    @classmethod
    def _validar_apellidos(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return validar_nombre_persona(v, "El apellido") if v else None

    @field_validator("curp")
    @classmethod
    def _validar_curp(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return validar_curp(v) if v else None


class PacienteResponse(BaseModel):
    id_PK: int
    clinica_id_FK: int | None = None
    nombre: str
    apellido: str
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    curp: str | None = None
    fecha_nacimiento: date | None
    genero: str | None
    telefono: str | None
    direccion: str | None
    correo_electronico: EmailStr | None
    estado: str | None

    class Config:
        from_attributes = True


class AlergiaCrear(BaseModel):
    nombre: str
    severidad: str | None = "moderada"
    notas: str | None = None
