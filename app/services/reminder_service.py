import asyncio
import logging
from datetime import datetime, date, time, timedelta
from typing import Set

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.services.citas_notification_service import notificar_recordatorio_cita

logger = logging.getLogger("vitalia.reminder_service")

recordatorios_24h_enviados: Set[int] = set()
recordatorios_1h_enviados: Set[int] = set()
_tarea_recordatorios_activa = False


async def verificar_y_emitir_recordatorios(db: Session):
    """Consulta citas próximas en las siguientes 24 horas y emite recordatorios por WebSocket (CU-11)."""
    ahora = datetime.now()
    limite_24h = ahora + timedelta(hours=24)

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    citas_proximas = (
        db.query(Cita)
        .filter(
            Cita.fecha >= ahora.date(),
            Cita.fecha <= limite_24h.date(),
            Cita.estado.notin_(["cancelada", "atendido", "finalizada"])
        )
        .all()
    )

    for cita in citas_proximas:
        if not cita.fecha or not cita.hora_inicio:
            continue

        fecha_cita = cita.fecha
        hora_cita = cita.hora_inicio
        cita_dt = datetime.combine(fecha_cita, hora_cita)

        diferencia_segundos = (cita_dt - ahora).total_seconds()
        if diferencia_segundos < 0:
            continue

        horas_restantes = int(diferencia_segundos // 3600)

        # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
        paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
        doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

        paciente_nombre = f"{paciente.nombre} {paciente.apellido}" if paciente else f"Paciente #{cita.paciente_id_FK}"
        doctor_nombre = doctor.nombre if doctor else f"Doctor #{cita.doctor_id_FK}"

        target_ids = []
        if paciente and getattr(paciente, "usuario_id_FK", None):
            target_ids.append(f"user_{paciente.usuario_id_FK}")
        if doctor and getattr(doctor, "usuario_id_FK", None):
            target_ids.append(f"user_{doctor.usuario_id_FK}")

        doctor_uid = doctor.usuario_id_FK if doctor else None
        paciente_uid = getattr(paciente, "usuario_id_FK", None) if paciente else None

        if diferencia_segundos <= 3600 and cita.id_PK not in recordatorios_1h_enviados:
            recordatorios_1h_enviados.add(cita.id_PK)
            await notificar_recordatorio_cita(
                db=db,
                cita_id=cita.id_PK,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=fecha_cita.isoformat(),
                hora=hora_cita.strftime("%H:%M"),
                horas_restantes=max(1, horas_restantes),
                doctor_usuario_id=doctor_uid,
                paciente_usuario_id=paciente_uid
            )
        elif diferencia_segundos <= 86400 and cita.id_PK not in recordatorios_24h_enviados:
            recordatorios_24h_enviados.add(cita.id_PK)
            await notificar_recordatorio_cita(
                db=db,
                cita_id=cita.id_PK,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=fecha_cita.isoformat(),
                hora=hora_cita.strftime("%H:%M"),
                horas_restantes=max(1, horas_restantes),
                doctor_usuario_id=doctor_uid,
                paciente_usuario_id=paciente_uid
            )


async def ciclo_recordatorios_background(intervalo_segundos: int = 60):
    """Bucle asíncrono en segundo plano para verificar periódicamente recordatorios de citas."""
    global _tarea_recordatorios_activa
    _tarea_recordatorios_activa = True
    logger.info("Servicio de recordatorios automáticos de citas iniciado en segundo plano.")

    while _tarea_recordatorios_activa:
        db = SessionLocal()
        try:
            await verificar_y_emitir_recordatorios(db)
        except Exception as e:
            logger.error(f"Error en el ciclo de recordatorios de citas: {e}")
        finally:
            db.close()

        await asyncio.sleep(intervalo_segundos)


def detener_ciclo_recordatorios():
    """Detiene la ejecución del ciclo en segundo plano de recordatorios."""
    global _tarea_recordatorios_activa
    _tarea_recordatorios_activa = False
