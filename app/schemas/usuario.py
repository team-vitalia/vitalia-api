from pydantic import BaseModel, EmailStr


class UsuarioCrear(BaseModel):
    nombre: str
    correo_electronico: EmailStr
    password: str
    rol_id_FK: int


class UsuarioResponse(BaseModel):
    id_PK: int
    nombre: str
    correo_electronico: EmailStr
    rol_id_FK: int | None
    estado: str | None

    class Config:
        from_attributes = True