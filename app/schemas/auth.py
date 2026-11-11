from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    correo_electronico: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class GoogleLoginRequest(BaseModel):
    token: str | None = None
    id_token: str | None = None
    access_token: str | None = None
