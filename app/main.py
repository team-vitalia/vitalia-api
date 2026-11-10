import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario

from app.routers.medicamentos import router as medicamentos_router
from app.routers.recetas import router as recetas_router

from app.routers.auth import router as auth_router
from app.routers.recuperacion import router as recuperacion_router
from app.routers.roles import router as roles_router
from app.routers.usuarios import router as usuarios_router
from app.routers.pacientes import router as pacientes_router
from app.routers.citas import router as citas_router
from app.routers.doctores import router as doctores_router
from app.routers.especialidades import router as especialidades_router
from app.routers.websocket import router as websocket_router, email_prueba
from app.routers.contratos import router as contratos_router
from app.routers.calendar import router as calendar_router
from app.routers.colas import router as colas_router
from app.routers.asistente_ia import router as asistente_ia_router

from app.routers.almacen import router as almacen_router
from app.routers.notificaciones import router as notificaciones_router

# Módulo C2 (Salas, Equipamiento, Auditoría y Reportes)
from app.routers.salas import router as salas_router
from app.routers.equipamiento import router as equipamiento_router
from app.routers.auditoria import router as auditoria_router
from app.routers.reportes import router as reportes_router
from app.routers.doctor_salas import router as doctor_salas_router

from app.routers.webhooks import router as webhooks_router

# Módulos de flujo clínico (consultas, expediente, espera, transferencias)
from app.routers.consultas import router as consultas_router
from app.routers.expediente import router as expediente_router
from app.routers.lista_espera import router as lista_espera_router
from app.routers.transferencias import router as transferencias_router
from app.routers.analitica_almacen import router as analitica_almacen_router
from app.routers.suscripciones import router as suscripciones_router
from app.routers.superadmin import router as superadmin_router

app = FastAPI(
    title="VITALIA API",
    description="API del sistema de gestión integral de clínicas VITALIA",
    version="1.0.0",
)

# Configuración de CORS habilitada para desarrollo y producción
origenes_cors = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
    "https://landing-ten-sigma-42.vercel.app",
    "https://vitalia-app-fowe.vercel.app",
]

cors_env = os.getenv("CORS_ORIGINS", "")
if cors_env:
    for o in cors_env.split(","):
        clean_o = o.strip().rstrip("/")
        if clean_o and clean_o not in origenes_cors:
            origenes_cors.append(clean_o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_cors,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rutas principales
app.include_router(auth_router)
app.include_router(recuperacion_router)
app.include_router(roles_router)
app.include_router(usuarios_router)
app.include_router(pacientes_router)
app.include_router(citas_router)
app.include_router(doctores_router)
app.include_router(especialidades_router)
app.include_router(websocket_router)
app.include_router(contratos_router)
app.include_router(calendar_router)
app.include_router(colas_router)
app.include_router(asistente_ia_router)

# Registro de rutas del Módulo A3 (Almacén e Inventarios)
app.include_router(almacen_router)
app.include_router(notificaciones_router)

# Registro de rutas del Módulo C2
app.include_router(salas_router)
app.include_router(equipamiento_router)
app.include_router(auditoria_router)
app.include_router(reportes_router)
app.include_router(doctor_salas_router)

app.include_router(medicamentos_router)
app.include_router(recetas_router)
app.include_router(webhooks_router)
app.include_router(suscripciones_router)
app.include_router(superadmin_router)
app.include_router(consultas_router)
app.include_router(expediente_router)
app.include_router(lista_espera_router)
app.include_router(transferencias_router)
app.include_router(analitica_almacen_router)
app.add_api_route("/email-prueba", email_prueba, methods=["POST"])


@app.on_event("startup")
async def iniciar_servicios_background():
    """Inicia tareas en segundo plano como el ciclo de recordatorios de citas."""
    import asyncio
    from app.services.reminder_service import ciclo_recordatorios_background
    asyncio.create_task(ciclo_recordatorios_background(intervalo_segundos=60))


@app.on_event("shutdown")
def detener_servicios_background():
    """Detiene tareas en segundo plano al apagar la aplicación."""
    from app.services.reminder_service import detener_ciclo_recordatorios
    detener_ciclo_recordatorios()


@app.get("/")
def root():
    return {
        "mensaje": "VITALIA API funcionando"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/health/database")
def health_database(
    db: Session = Depends(get_db),
):
    resultado = db.execute(text("SELECT 1"))

    return {
        "database": "conectada",
        "resultado": resultado.scalar(),
    }


@app.get("/api/auth/me")
def obtener_usuario_actual(
    usuario: Usuario = Depends(get_current_user),
):
    clinica_data = None
    if usuario.clinica:
        plan = usuario.clinica.plan
        clinica_data = {
            "id": usuario.clinica.id_PK,
            "nombre_comercial": usuario.clinica.nombre_comercial,
            "activa": usuario.clinica.activa,
            "plan_actual": {
                "nombre_plan": plan.nombre if plan else "Básico",
                "incluye_ia": (plan.limite_ia_mensual > 0) if plan else False,
                "incluye_calendar": plan.incluye_calendar if plan else False,
                "incluye_contratos": plan.incluye_contratos if plan else False,
                "limite_personal": plan.limite_personal if plan else 3,
                "limite_pacientes": plan.limite_pacientes if plan else 100,
                "limite_ia_mensual": plan.limite_ia_mensual if plan else 0,
                "precio_mensual": plan.precio_mensual if plan else 599.0,
            } if plan else {
                "nombre_plan": "Básico",
                "incluye_ia": False,
                "incluye_calendar": False,
                "incluye_contratos": False,
                "limite_personal": 3,
                "limite_pacientes": 100,
                "limite_ia_mensual": 0,
                "precio_mensual": 599.0,
            }
        }

    return {
        "id": usuario.id_PK,
        "nombre": usuario.nombre,
        "correo": usuario.correo_electronico,
        "rol_id": usuario.rol_id_FK,
        "estado": usuario.estado,
        "clinica": clinica_data,
    }
