"""Esquemas Pydantic para el flujo de pre-registro y suscripciones SaaS."""

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
