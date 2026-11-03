from pydantic import BaseModel, EmailStr, Field

PASSWORD_MIN = 8
PASSWORD_MAX = 128


class SolicitudCodigoCorreo(BaseModel):
    correo_electronico: EmailStr


class ConfirmarCodigoCorreo(BaseModel):
    correo_electronico: EmailStr
    codigo: str = Field(pattern=r"^\d{6}$")
    nueva_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class ConfirmarQR(BaseModel):
    usuario_id: int = Field(gt=0)
    token: str = Field(min_length=20, max_length=100)
    nueva_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
