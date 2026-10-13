import logging
from datetime import datetime, date, time
from typing import Optional

from app.services.calendar_service import calendar_service

logger = logging.getLogger("vitalia.citas_calendar")


def _obtener_credenciales_usuario(user_id: str):
    """Recupera las credenciales de Google Calendar asociadas al usuario o fallback a default."""
    creds = calendar_service.get_user_credentials(user_id)
    if not creds:
        creds = calendar_service.get_user_credentials("default_user")
    return creds


def sincronizar_creacion_google_calendar(
    user_id: str,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    paciente_nombre: str,
    doctor_nombre: str,
    motivo: Optional[str] = None
) -> Optional[str]:
    """Inserta automáticamente la cita en Google Calendar con manejo seguro de fallback si no hay conexión."""
    try:
        creds = _obtener_credenciales_usuario(user_id)
        if not creds:
            logger.info(f"Usuario '{user_id}' no tiene Google Calendar vinculado. Cita guardada localmente.")
            return None

        inicio_dt = datetime.combine(fecha, hora_inicio)
        fin_dt = datetime.combine(fecha, hora_fin)
        resumen = f"Cita Médica VITALIA - Dr. {doctor_nombre}"
        descripcion = f"Paciente: {paciente_nombre}\nMotivo: {motivo or 'Consulta general'}\nRegistrado en Vitalia."

        evento = calendar_service.create_appointment_event(
            credentials=creds,
            summary=resumen,
            description=descripcion,
            start_time=inicio_dt,
            end_time=fin_dt
        )
        return evento.get("id")
    except Exception as e:
        logger.warning(f"Fallback activado: Falló sincronización con Google Calendar al crear: {e}")
        return None


def sincronizar_actualizacion_google_calendar(
    user_id: str,
    event_id: Optional[str],
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    paciente_nombre: str,
    doctor_nombre: str,
    motivo: Optional[str] = None
) -> Optional[str]:
    """Actualiza o crea la cita en Google Calendar al reprogramar con fallback ante errores."""
    if not event_id:
        return sincronizar_creacion_google_calendar(
            user_id, fecha, hora_inicio, hora_fin, paciente_nombre, doctor_nombre, motivo
        )

    try:
        creds = _obtener_credenciales_usuario(user_id)
        if not creds:
            logger.info(f"Usuario '{user_id}' sin Google Calendar. Cita reprogramada localmente.")
            return event_id

        inicio_dt = datetime.combine(fecha, hora_inicio)
        fin_dt = datetime.combine(fecha, hora_fin)
        resumen = f"Cita Médica VITALIA (Reprogramada) - Dr. {doctor_nombre}"
        descripcion = f"Paciente: {paciente_nombre}\nMotivo: {motivo or 'Consulta general'}\nReprogramado en Vitalia."

        calendar_service.update_event(
            credentials=creds,
            event_id=event_id,
            summary=resumen,
            description=descripcion,
            start_time=inicio_dt,
            end_time=fin_dt
        )
        return event_id
    except Exception as e:
        logger.warning(f"Fallback activado: Falló actualización en Google Calendar ({event_id}): {e}")
        return event_id


def sincronizar_eliminacion_google_calendar(user_id: str, event_id: Optional[str]) -> bool:
    """Elimina el evento en Google Calendar si existe al cancelar la cita con fallback ante errores."""
    if not event_id:
        return True

    try:
        creds = _obtener_credenciales_usuario(user_id)
        if not creds:
            return True

        calendar_service.delete_event(creds, event_id)
        return True
    except Exception as e:
        logger.warning(f"Fallback activado: No se pudo eliminar evento {event_id} de Google Calendar: {e}")
        return False
