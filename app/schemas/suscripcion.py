from pydantic import BaseModel, ConfigDict, EmailStr


class PreRegistroRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_clinica: str
    nombre_admin: str
    correo: EmailStr
    password: str
    paypal_plan_id: str


class PreRegistroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinica_id: int
    mensaje: str


class ConfirmarSuscripcionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    clinica_id: int | None = None
    paypal_plan_id: str | None = None
    correo: str | None = None
    nombre_clinica: str | None = None
    nombre_admin: str | None = None


class ConfirmarSuscripcionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    clinica_id: int
    activa: bool
    mensaje: str
    nombre_plan: str | None = None
