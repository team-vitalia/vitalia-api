import datetime
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.notificacion import Notificacion
from app.services.connection_manager import manager

logger = logging.getLogger("vitalia.citas_notification")


def guardar_notificacion_bd(
    db: Session,
    usuario_id: int,
    mensaje: str,
    tipo: str,
    enlace: Optional[str] = None
) -> Optional[Notificacion]:
    try:
        notif = Notificacion(
            usuario_id_FK=usuario_id,
            mensaje=mensaje,
            tipo=tipo,
            estado="no_leido",
            creado_en=datetime.datetime.now(),
            enlace=enlace,
            leido_en=None
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif
    except Exception as e:
        db.rollback()
        logger.error(f"Error guardando notificación en BD para usuario {usuario_id}: {e}")
        return None


async def notificar_cita_creada(
    db: Session,
    cita_id: int,
    paciente_nombre: str,
    doctor_nombre: str,
    fecha: str,
    hora: str,
    doctor_usuario_id: Optional[int] = None,
    creador_usuario_id: Optional[int] = None,
    paciente_usuario_id: Optional[int] = None
):
    texto_doctor = f"Nueva cita {cita_id} asignada para {paciente_nombre} el {fecha} a las {hora}."
    texto_recepcion = f"Nueva cita {cita_id} registrada para {paciente_nombre} con Dr. {doctor_nombre} el {fecha} a las {hora}."

    notif_doctor_id = None
    if doctor_usuario_id:
        notif_doc = guardar_notificacion_bd(
            db=db,
            usuario_id=doctor_usuario_id,
            mensaje=texto_doctor,
            tipo="appointment_created",
            enlace="/doctor/consultas"
        )
        if notif_doc:
            notif_doctor_id = notif_doc.id_PK

    notif_creador_id = None
    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        notif_cre = guardar_notificacion_bd(
            db=db,
            usuario_id=creador_usuario_id,
            mensaje=texto_recepcion,
            tipo="appointment_created",
            enlace="/recepcion/citas"
        )
        if notif_cre:
            notif_creador_id = notif_cre.id_PK

    if paciente_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=paciente_usuario_id,
            mensaje=f"Tu cita médica con Dr. {doctor_nombre} ha sido confirmada para el {fecha} a las {hora}.",
            tipo="appointment_created",
            enlace="/paciente"
        )

    payload_base = {
        "type": "appointment_created",
        "title": "Cita Confirmada",
        "body": texto_recepcion,
        "cita_id": cita_id,
        "paciente": paciente_nombre,
        "doctor": doctor_nombre,
        "fecha": fecha,
        "hora": hora,
        "timestamp": datetime.datetime.now().isoformat()
    }

    if doctor_usuario_id:
        payload_doc = dict(payload_base)
        payload_doc["body"] = texto_doctor
        if notif_doctor_id:
            payload_doc["notificacion_id"] = notif_doctor_id
        await manager.send_personal_message(payload_doc, f"user_{doctor_usuario_id}")

    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        payload_cre = dict(payload_base)
        if notif_creador_id:
            payload_cre["notificacion_id"] = notif_creador_id
        await manager.send_personal_message(payload_cre, f"user_{creador_usuario_id}")

    if paciente_usuario_id:
        payload_pac = dict(payload_base)
        payload_pac["body"] = f"Tu cita médica con Dr. {doctor_nombre} ha sido confirmada para el {fecha} a las {hora}."
        await manager.send_personal_message(payload_pac, f"user_{paciente_usuario_id}")

    if not doctor_usuario_id and not creador_usuario_id and not paciente_usuario_id:
        await manager.broadcast(payload_base)


async def notificar_cita_reprogramada(
    db: Session,
    cita_id: int,
    paciente_nombre: str,
    doctor_nombre: str,
    nueva_fecha: str,
    nueva_hora: str,
    doctor_usuario_id: Optional[int] = None,
    creador_usuario_id: Optional[int] = None,
    paciente_usuario_id: Optional[int] = None
):
    texto_doctor = f"La cita {cita_id} con {paciente_nombre} fue reprogramada para el {nueva_fecha} a las {nueva_hora}."
    texto_recepcion = f"La cita {cita_id} ({paciente_nombre}) fue reprogramada para el {nueva_fecha} a las {nueva_hora}."

    notif_doctor_id = None
    if doctor_usuario_id:
        notif_doc = guardar_notificacion_bd(
            db=db,
            usuario_id=doctor_usuario_id,
            mensaje=texto_doctor,
            tipo="appointment_rescheduled",
            enlace="/doctor/consultas"
        )
        if notif_doc:
            notif_doctor_id = notif_doc.id_PK

    notif_creador_id = None
    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        notif_cre = guardar_notificacion_bd(
            db=db,
            usuario_id=creador_usuario_id,
            mensaje=texto_recepcion,
            tipo="appointment_rescheduled",
            enlace="/recepcion/citas"
        )
        if notif_cre:
            notif_creador_id = notif_cre.id_PK

    if paciente_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=paciente_usuario_id,
            mensaje=f"Tu cita con Dr. {doctor_nombre} fue reprogramada para el {nueva_fecha} a las {nueva_hora}.",
            tipo="appointment_rescheduled",
            enlace="/paciente"
        )

    payload_base = {
        "type": "appointment_rescheduled",
        "title": "Cita Reprogramada",
        "body": texto_recepcion,
        "cita_id": cita_id,
        "paciente": paciente_nombre,
        "doctor": doctor_nombre,
        "fecha": nueva_fecha,
        "hora": nueva_hora,
        "timestamp": datetime.datetime.now().isoformat()
    }

    if doctor_usuario_id:
        payload_doc = dict(payload_base)
        payload_doc["body"] = texto_doctor
        if notif_doctor_id:
            payload_doc["notificacion_id"] = notif_doctor_id
        await manager.send_personal_message(payload_doc, f"user_{doctor_usuario_id}")

    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        payload_cre = dict(payload_base)
        if notif_creador_id:
            payload_cre["notificacion_id"] = notif_creador_id
        await manager.send_personal_message(payload_cre, f"user_{creador_usuario_id}")

    if paciente_usuario_id:
        payload_pac = dict(payload_base)
        payload_pac["body"] = f"Tu cita con Dr. {doctor_nombre} fue reprogramada para el {nueva_fecha} a las {nueva_hora}."
        await manager.send_personal_message(payload_pac, f"user_{paciente_usuario_id}")

    if not doctor_usuario_id and not creador_usuario_id and not paciente_usuario_id:
        await manager.broadcast(payload_base)


async def notificar_cita_cancelada(
    db: Session,
    cita_id: int,
    paciente_nombre: str,
    doctor_nombre: str,
    doctor_usuario_id: Optional[int] = None,
    creador_usuario_id: Optional[int] = None,
    paciente_usuario_id: Optional[int] = None
):
    texto_doctor = f"La cita {cita_id} de {paciente_nombre} ha sido cancelada."
    texto_recepcion = f"La cita {cita_id} de {paciente_nombre} con Dr. {doctor_nombre} ha sido cancelada."

    if doctor_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=doctor_usuario_id,
            mensaje=texto_doctor,
            tipo="appointment_cancelled",
            enlace="/doctor/consultas"
        )

    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=creador_usuario_id,
            mensaje=texto_recepcion,
            tipo="appointment_cancelled",
            enlace="/recepcion/citas"
        )

    if paciente_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=paciente_usuario_id,
            mensaje=f"Tu cita con Dr. {doctor_nombre} ha sido cancelada.",
            tipo="appointment_cancelled",
            enlace="/paciente"
        )

    payload_base = {
        "type": "appointment_cancelled",
        "title": "Cita Cancelada",
        "body": texto_recepcion,
        "cita_id": cita_id,
        "paciente": paciente_nombre,
        "doctor": doctor_nombre,
        "timestamp": datetime.datetime.now().isoformat()
    }

    if doctor_usuario_id:
        payload_doc = dict(payload_base)
        payload_doc["body"] = texto_doctor
        await manager.send_personal_message(payload_doc, f"user_{doctor_usuario_id}")

    if creador_usuario_id and creador_usuario_id != doctor_usuario_id:
        await manager.send_personal_message(payload_base, f"user_{creador_usuario_id}")

    if paciente_usuario_id:
        payload_pac = dict(payload_base)
        payload_pac["body"] = f"Tu cita con Dr. {doctor_nombre} ha sido cancelada."
        await manager.send_personal_message(payload_pac, f"user_{paciente_usuario_id}")

    if not doctor_usuario_id and not creador_usuario_id and not paciente_usuario_id:
        await manager.broadcast(payload_base)


async def notificar_recordatorio_cita(
    db: Session,
    cita_id: int,
    paciente_nombre: str,
    doctor_nombre: str,
    fecha: str,
    hora: str,
    horas_restantes: int,
    doctor_usuario_id: Optional[int] = None,
    paciente_usuario_id: Optional[int] = None
):
    texto_tiempo = "en 1 hora" if horas_restantes <= 1 else f"en aprox. {horas_restantes} horas"
    texto = f"Recordatorio: Cita {cita_id} ({texto_tiempo}) para {paciente_nombre} con Dr. {doctor_nombre} el {fecha} a las {hora}."

    if doctor_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=doctor_usuario_id,
            mensaje=f"Recordatorio ({texto_tiempo}): Consulta con {paciente_nombre} programada para hoy {fecha} a las {hora}.",
            tipo="appointment_reminder",
            enlace="/doctor/consultas"
        )

    if paciente_usuario_id:
        guardar_notificacion_bd(
            db=db,
            usuario_id=paciente_usuario_id,
            mensaje=f"Recordatorio ({texto_tiempo}): Tienes cita con Dr. {doctor_nombre} el {fecha} a las {hora}.",
            tipo="appointment_reminder",
            enlace="/paciente"
        )

    payload = {
        "type": "appointment_reminder",
        "title": "Recordatorio de Cita Médica",
        "body": texto,
        "cita_id": cita_id,
        "paciente": paciente_nombre,
        "doctor": doctor_nombre,
        "fecha": fecha,
        "hora": hora,
        "horas_restantes": horas_restantes,
        "timestamp": datetime.datetime.now().isoformat()
    }

    if doctor_usuario_id:
        await manager.send_personal_message(payload, f"user_{doctor_usuario_id}")
    if paciente_usuario_id:
        await manager.send_personal_message(payload, f"user_{paciente_usuario_id}")
    if not doctor_usuario_id and not paciente_usuario_id:
        await manager.broadcast(payload)
