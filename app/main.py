from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario

from app.routers.auth import router as auth_router
from app.routers.roles import router as roles_router
from app.routers.usuarios import router as usuarios_router
from app.routers.pacientes import router as pacientes_router
from app.routers.citas import router as citas_router
from app.routers.doctores import router as doctores_router
from app.routers.especialidades import router as especialidades_router
from app.routers.websocket import router as websocket_router
from app.routers.contratos import router as contratos_router
from app.routers.calendar import router as calendar_router
from app.routers.colas import router as colas_router

from app.routers.almacen import router as almacen_router
from app.routers.notificaciones import router as notificaciones_router

app = FastAPI(
    title="VITALIA API",
    description="API del sistema de gestión integral de clínicas VITALIA",
    version="1.0.0",
)

# Configuración de CORS habilitada para Expo y navegadores web
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:19006",
        "http://127.0.0.1:19006",
        "*",  # Permite peticiones durante desarrollo
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rutas principales
app.include_router(auth_router)
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

# Registro de rutas del Módulo A3 (Almacén e Inventarios)
app.include_router(almacen_router)
app.include_router(notificaciones_router)


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
    return {
        "id": usuario.id_PK,
        "nombre": usuario.nombre,
        "correo": usuario.correo_electronico,
        "rol_id": usuario.rol_id_FK,
        "estado": usuario.estado,
    }