from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    correo_electronico: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str