import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel

from app.services.calendar_service import calendar_service

logger = logging.getLogger("vitalia.calendar_router")

router = APIRouter(
    prefix="/calendar",
    tags=["Google Calendar"]
)


class AuthCallbackRequest(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    code: Optional[str] = None
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None
    user_id: Optional[str] = "default_user"


class CreateEventRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    access_token: Optional[str] = None
    summary: Optional[str] = "Cita Médica VITALIA - Prueba"
    description: Optional[str] = "Cita médica agendada desde el sistema integral VITALIA."
    start_time: Optional[str] = None
    duration_minutes: Optional[int] = 60


class DeleteEventRequest(BaseModel):
    event_id: str
    user_id: Optional[str] = "default_user"
    access_token: Optional[str] = None


class DisconnectRequest(BaseModel):
    user_id: Optional[str] = "default_user"


@router.get("/status")
@router.get("/status/{user_id}")
async def get_calendar_status(user_id: Optional[str] = "default_user"):
    """
    Verifica si el usuario tiene una vinculación permanente de Google Calendar activa en el servidor.
    Permite a la aplicación saber si el servicio está activo sin depender de tokens en el navegador.
    """
    is_connected = calendar_service.is_user_connected(user_id or "default_user")
    user_data = calendar_service.tokens_cache.get(user_id or "default_user", {})
    return {
        "status": "success",
        "user_id": user_id,
        "is_connected": is_connected,
        "has_refresh_token": bool(user_data.get("refresh_token")),
        "updated_at": user_data.get("updated_at")
    }


@router.post("/auth/callback")
async def calendar_auth_callback(payload: AuthCallbackRequest):
    """
    Recibe el token o código del frontend, genera las credenciales de Google
    y las persiste permanentemente en el servidor para uso autónomo.
    """
    try:
        user_id = payload.user_id or "default_user"

        if payload.code:
            redirect_uri = payload.redirect_uri or "http://localhost:8081"
            creds = calendar_service.exchange_code_for_credentials(
                code=payload.code,
                redirect_uri=redirect_uri,
                code_verifier=payload.code_verifier
            )
            calendar_service.save_user_credentials(
                user_id=user_id,
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                expiry=creds.expiry.isoformat() if creds.expiry else None
            )
            return {
                "status": "success",
                "message": "Credenciales de Google Calendar guardadas permanentemente en el servidor.",
                "user_id": user_id,
                "is_connected": True
            }

        elif payload.access_token:
            calendar_service.save_user_credentials(
                user_id=user_id,
                access_token=payload.access_token,
                refresh_token=payload.refresh_token
            )
            return {
                "status": "success",
                "message": "Token de Google Calendar vinculado exitosamente en el servidor.",
                "user_id": user_id,
                "is_connected": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere 'access_token' o 'code' para autenticar con Google Calendar."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en /calendar/auth/callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar autenticación de Google: {str(e)}"
        )


@router.post("/auth/disconnect")
async def disconnect_calendar(payload: DisconnectRequest):
    """
    Desvincula la cuenta de Google Calendar del usuario en el servidor.
    """
    user_id = payload.user_id or "default_user"
    desvinculado = calendar_service.disconnect_user(user_id)
    return {
        "status": "success",
        "message": "Servicio de Google Calendar desvinculado del servidor.",
        "user_id": user_id,
        "is_connected": False
    }


@router.post("/event/create")
async def create_calendar_event(payload: CreateEventRequest):
    """
    Crea una cita médica en Google Calendar.
    Utiliza automáticamente las credenciales guardadas en el servidor y las renueva si están vencidas.
    """
    try:
        user_id = payload.user_id or "default_user"

        # 1. Intentar obtener credenciales persistentes del servidor con autorenovación
        creds = calendar_service.get_user_credentials(user_id)

        # 2. Si no están en el servidor pero vienen en la petición, usarlas directamente
        if not creds and payload.access_token:
            creds = calendar_service.build_credentials_from_token(payload.access_token)

        if not creds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No hay credenciales activas de Google Calendar para este usuario en el servidor. Vincula tu cuenta primero."
            )

        start_dt = None
        if payload.start_time:
            start_dt = datetime.fromisoformat(payload.start_time)

        evento = calendar_service.create_test_event(
            credentials=creds,
            summary=payload.summary or "Cita Médica VITALIA - Prueba",
            description=payload.description or "Cita médica agendada desde el sistema integral VITALIA.",
            start_time=start_dt,
            duration_minutes=payload.duration_minutes or 60
        )

        return {
            "status": "success",
            "message": "Evento creado exitosamente en Google Calendar.",
            "event_id": evento.get("id"),
            "html_link": evento.get("htmlLink"),
            "summary": evento.get("summary"),
            "start": evento.get("start"),
            "end": evento.get("end")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear evento en Google Calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de Google Calendar: {str(e)}"
        )


@router.post("/event/delete")
async def delete_calendar_event(payload: DeleteEventRequest):
    """
    Elimina una cita médica de Google Calendar.
    """
    try:
        user_id = payload.user_id or "default_user"

        creds = calendar_service.get_user_credentials(user_id)
        if not creds and payload.access_token:
            creds = calendar_service.build_credentials_from_token(payload.access_token)

        if not creds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No hay credenciales activas de Google Calendar para este usuario en el servidor."
            )

        calendar_service.delete_event(creds, payload.event_id)

        return {
            "status": "success",
            "message": f"Evento {payload.event_id} eliminado exitosamente de Google Calendar.",
            "event_id": payload.event_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar evento en Google Calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar evento: {str(e)}"
        )
