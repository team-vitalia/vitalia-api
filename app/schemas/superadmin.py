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
    precio_anual: float = 0.0
    limite_personal: int = 0
    limite_pacientes: int = 0
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


class ClinicaPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: int


class MetricaItemMes(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mes: str
    ingresos: float
    nuevas_clinicas: int
    nuevos_usuarios: int


class MetricasSuperadminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_clinicas: int
    clinicas_activas: int
    clinicas_inactivas: int
    ingresos_mensuales: float
    proyeccion_anual: float = 0.0
    total_planes: int
    total_usuarios: int
    usuarios_activos: int = 0
    usuarios_nuevos_mes: int = 0
    tasa_crecimiento_usuarios: float = 0.0
    historico_6_meses: list[MetricaItemMes] = []


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


class UsoRecursoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actual: float
    limite: float
    porcentaje: float
    unidad: str


class AuditoriaAccesoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario_id: int
    nombre_usuario: str
    rol: str
    correo: str
    ultimo_acceso: datetime | None = None


class AuditoriaActividadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario: str
    accion: str
    descripcion: str | None = None
    marca_tiempo: datetime
    nombre_tabla: str | None = None


class MetricasClinicaIndividualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinica_id: int
    nombre_comercial: str
    activa: bool
    fecha_registro: datetime
    plan: PlanClinicaOut | None = None
    paypal_subscription_id: str | None = None
    estado_suscripcion: str
    proximo_ciclo_facturacion: datetime | None = None
    citas_mes_actual: int = 0
    citas_mes_anterior: int = 0
    uso_personal: UsoRecursoOut
    uso_pacientes: UsoRecursoOut
    uso_almacenamiento: UsoRecursoOut
    candidato_upsell: bool = False
    motivos_upsell: list[str] = []
    administradores: list[AdministradorClinicaOut] = []
    ultimos_accesos: list[AuditoriaAccesoOut] = []
    actividades_recientes: list[AuditoriaActividadOut] = []
