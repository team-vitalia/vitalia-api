from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class AdministradorClinicaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_completo: str
    correo_electronico: EmailStr
    estado: str | None = None
    ultimo_acceso: datetime | None = None


class PlanClinicaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    precio_mensual: float
    paypal_plan_id: str | None = None


class ClinicaSuperadminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_comercial: str
    activa: bool
    fecha_registro: datetime
    paypal_subscription_id: str | None = None
    plan: PlanClinicaOut | None = None
    administradores: list[AdministradorClinicaOut] = []
    total_usuarios: int = 0
    total_pacientes: int = 0


class ClinicaEstadoUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activa: bool


class MetricasSuperadminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_clinicas: int
    clinicas_activas: int
    clinicas_inactivas: int
    ingresos_mensuales: float
    total_planes: int
    total_usuarios: int


class PlanSuperadminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    precio_mensual: float
    precio_anual: float
    limite_personal: int
    limite_pacientes: int
    incluye_calendar: bool
    incluye_correos: bool
    limite_ia_mensual: int
    paypal_plan_id: str | None = None
    clinicas_activas_count: int = 0
