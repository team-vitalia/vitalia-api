from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class PreRegistroRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_clinica: str
    nombre_admin: str
    correo: EmailStr
    password: str | None = None
    paypal_plan_id: str
    auth_provider: str | None = "manual"
    google_token: str | None = None


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
    modo: str | None = None
    es_upgrade: bool | None = False


class ConfirmarSuscripcionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    clinica_id: int
    activa: bool
    mensaje: str
    nombre_plan: str | None = None


class RegistroGratuitoRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_clinica: str | None = None
    nombre_doctor: str | None = None
    nombre: str | None = None
    correo: EmailStr
    password: str


class RegistroGratuitoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    access_token: str
    token_type: str
    clinica_id: int
    nombre_clinica: str
    nombre_plan: str
    mensaje: str
    usuario_id: int


class CancelarSuscripcionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    motivo_categoria: str
    comentarios_adicionales: str | None = None
    solicitar_reembolso: bool = False


class CancelarSuscripcionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    mensaje: str
    clinica_id: int
    plan_actual: str
    aplica_reembolso: bool
    estado_reembolso: str
    paypal_refund_id: str | None = None
    fecha_cancelacion: datetime
