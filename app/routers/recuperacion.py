import os
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.services.email_service import enviar_correo
from app.services.recuperacion_service import (
    ESPERA_REENVIO_SEGUNDOS,
    TIPO_CORREO,
    TIPO_QR,
    TTL_SEGUNDOS,
    cambiar_password,
    emitir,
    generar_token_correo,
    generar_token_qr,
    html_enlace_recuperacion,
    limpiar,
    puede_reenviar,
    validar,
)

router = APIRouter(prefix="/api/auth/recuperar", tags=["Recuperación de contraseña"])
PASSWORD_MIN = 8
PASSWORD_MAX = 128


class SolicitudCodigoCorreo(BaseModel):
    correo_electronico: EmailStr


class ConfirmarEnlaceCorreo(BaseModel):
    usuario_id: int = Field(gt=0)
    token: str = Field(min_length=20, max_length=100)
    nueva_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class ConfirmarQR(BaseModel):
    usuario_id: int = Field(gt=0)
    token: str = Field(min_length=20, max_length=100)
    nueva_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


def _url_recuperacion(usuario_id: int, token: str, tipo: str) -> str:
    base = os.getenv("FRONTEND_RESET_URL", "http://localhost:8081/recuperar").strip()
    separador = "&" if "?" in base else "?"
    return f"{base}{separador}{urlencode({'usuario_id': usuario_id, 'token': token, 'tipo': tipo})}"


def _buscar_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id_PK == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="El enlace de recuperación no es válido o ha caducado.")
    return usuario


@router.post("/correo/solicitar")
async def solicitar_enlace_correo(datos: SolicitudCodigoCorreo, db: Session = Depends(get_db)):
    correo = str(datos.correo_electronico).strip().lower()
    usuario = db.query(Usuario).filter(Usuario.correo_electronico == correo).first()

    # Respuesta genérica para no revelar si existe una cuenta.
    respuesta_generica = {
        "mensaje": "Si la cuenta existe y está activa, recibirás un enlace de recuperación.",
        "espera_segundos": ESPERA_REENVIO_SEGUNDOS,
    }
    if not usuario or usuario.estado != "activo":
        return respuesta_generica

    if not puede_reenviar(usuario, TIPO_CORREO):
        datos_token = usuario.token_restablecimiento.split(":", 3)
        exp = int(datos_token[1])
        emitido_en = exp - TTL_SEGUNDOS[TIPO_CORREO]
        restante = max(1, ESPERA_REENVIO_SEGUNDOS - int(time.time() - emitido_en))
        respuesta_generica["espera_segundos"] = restante
        return respuesta_generica

    token = generar_token_correo()
    emitir(db, usuario, TIPO_CORREO, token)
    enlace = _url_recuperacion(usuario.id_PK, token, TIPO_CORREO)
    html = html_enlace_recuperacion(usuario.nombre, enlace)
    texto = (
        f"Hola {usuario.nombre}. Para cambiar tu contraseña abre este enlace: {enlace}\n"
        f"El enlace vence en {TTL_SEGUNDOS[TIPO_CORREO] // 60} minutos."
    )
    enviado = await enviar_correo(correo, "Restablecer contraseña - VITALIA", html, texto)
    if not enviado:
        limpiar(db, usuario)
        raise HTTPException(status_code=503, detail="No fue posible enviar el correo. Intenta más tarde.")
    return respuesta_generica


@router.post("/correo/confirmar")
def confirmar_enlace_correo(datos: ConfirmarEnlaceCorreo, db: Session = Depends(get_db)):
    usuario = _buscar_usuario(db, datos.usuario_id)
    if usuario.estado != "activo" or not validar(db, usuario, TIPO_CORREO, datos.token):
        raise HTTPException(status_code=400, detail="El enlace de recuperación no es válido o ha caducado.")
    cambiar_password(db, usuario, datos.nueva_password)
    return {"mensaje": "Tu contraseña se cambió correctamente. Ya puedes iniciar sesión."}


@router.post("/qr/generar/{usuario_id}")
def generar_qr(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    # En el proyecto actual los roles 1 y 5 tienen permiso para generar QR de recuperación.
    if usuario_actual.rol_id_FK not in [1, 5]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para generar QR de recuperación.")

    usuario = _buscar_usuario(db, usuario_id)
    if usuario.estado != "activo":
        raise HTTPException(status_code=400, detail="No se puede generar recuperación para un usuario inactivo.")
    if not puede_reenviar(usuario, TIPO_QR):
        raise HTTPException(status_code=429, detail="Espera 60 segundos antes de generar otro QR.")

    token = generar_token_qr()
    exp = emitir(db, usuario, TIPO_QR, token)
    payload = _url_recuperacion(usuario.id_PK, token, TIPO_QR)
    return {
        "payload": payload,
        "usuario": usuario.nombre,
        "expira_en": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(exp)),
        "segundos": TTL_SEGUNDOS[TIPO_QR],
    }


@router.post("/qr/confirmar")
def confirmar_qr(datos: ConfirmarQR, db: Session = Depends(get_db)):
    usuario = _buscar_usuario(db, datos.usuario_id)
    if usuario.estado != "activo" or not validar(db, usuario, TIPO_QR, datos.token):
        raise HTTPException(status_code=400, detail="El QR no es válido o ha caducado.")
    cambiar_password(db, usuario, datos.nueva_password)
    return {"mensaje": "Tu contraseña se cambió correctamente. Ya puedes iniciar sesión."}
