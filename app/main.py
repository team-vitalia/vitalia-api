from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.routers.auth import router as auth_router
from app.routers.roles import router as roles_router
from app.routers.usuarios import router as usuarios_router
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario

app = FastAPI(
    title="VITALIA API",
    description="API del sistema de gestión integral de clínicas VITALIA",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(usuarios_router)


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
    db: Session = Depends(get_db)
):
    resultado = db.execute(
        text("SELECT 1")
    )

    return {
        "database": "conectada",
        "resultado": resultado.scalar()
    }
    
@app.get("/api/auth/me")
def obtener_usuario_actual(
    usuario: Usuario = Depends(get_current_user)
):
    return {
        "id": usuario.id_PK,
        "nombre": usuario.nombre,
        "correo": usuario.correo_electronico,
        "rol_id": usuario.rol_id_FK,
        "estado": usuario.estado
    }