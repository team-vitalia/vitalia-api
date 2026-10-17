import asyncio
import logging
from datetime import datetime, date, time, timedelta
from typing import Set

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.services.citas_notification_service import notificar_recordatorio_cita
from app.services.email_service import notificar_correo_recordatorio

logger = logging.getLogger("vitalia.reminder_service")

recordatorios_7d_enviados: Set[int] = set()
recordatorios_24h_enviados: Set[int] = set()
recordatorios_1h_enviados: Set[int] = set()
_tarea_recordatorios_activa = False

async def verificar_y_emitir_recordatorios(db: Session):
    ahora = datetime.now()
    limite_7d = ahora + timedelta(days=8)

    citas_proximas = (
        db.query(Cita)
        .filter(
            Cita.fecha >= ahora.date(),
            Cita.fecha <= limite_7d.date(),
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

        paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
        doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

        paciente_nombre = f"{paciente.nombre} {paciente.apellido}" if paciente else f"Paciente {cita.paciente_id_FK}"
        doctor_nombre = doctor.nombre if doctor else f"Doctor {cita.doctor_id_FK}"

        doctor_uid = doctor.usuario_id_FK if doctor else None
        paciente_uid = getattr(paciente, "usuario_id_FK", None) if paciente else None
        
        correo_paciente = getattr(paciente, "correo_electronico", None)
        if not correo_paciente and paciente and paciente_uid:
            usuario_paciente = db.query(Usuario).filter(Usuario.id_PK == paciente_uid).first()
            if usuario_paciente:
                correo_paciente = usuario_paciente.correo_electronico

        hora_str = hora_cita.strftime("%H:%M")
        fecha_str = fecha_cita.isoformat()
        motivo_str = cita.motivo or "Consulta médica general"

        if 0 < diferencia_segundos <= 3600 and cita.id_PK not in recordatorios_1h_enviados:
            recordatorios_1h_enviados.add(cita.id_PK)
            recordatorios_24h_enviados.add(cita.id_PK)
            recordatorios_7d_enviados.add(cita.id_PK)

            await notificar_recordatorio_cita(
                db=db,
                cita_id=cita.id_PK,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=fecha_str,
                hora=hora_str,
                horas_restantes=1,
                doctor_usuario_id=doctor_uid,
                paciente_usuario_id=paciente_uid
            )

            if correo_paciente:
                asyncio.create_task(
                    notificar_correo_recordatorio(
                        destinatario=correo_paciente,
                        paciente_nombre=paciente_nombre,
                        doctor_nombre=doctor_nombre,
                        fecha=fecha_str,
                        hora=hora_str,
                        intervalo_texto="1 hora",
                        motivo=motivo_str
                    )
                )

        elif 3600 < diferencia_segundos <= 86400 and cita.id_PK not in recordatorios_24h_enviados:
            recordatorios_24h_enviados.add(cita.id_PK)
            recordatorios_7d_enviados.add(cita.id_PK)

            horas_restantes = max(1, int(diferencia_segundos // 3600))
            await notificar_recordatorio_cita(
                db=db,
                cita_id=cita.id_PK,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=fecha_str,
                hora=hora_str,
                horas_restantes=horas_restantes,
                doctor_usuario_id=doctor_uid,
                paciente_usuario_id=paciente_uid
            )

            if correo_paciente:
                asyncio.create_task(
                    notificar_correo_recordatorio(
                        destinatario=correo_paciente,
                        paciente_nombre=paciente_nombre,
                        doctor_nombre=doctor_nombre,
                        fecha=fecha_str,
                        hora=hora_str,
                        intervalo_texto="1 día (24 horas)",
                        motivo=motivo_str
                    )
                )

        elif 86400 < diferencia_segundos <= 604800 and cita.id_PK not in recordatorios_7d_enviados:
            recordatorios_7d_enviados.add(cita.id_PK)

            horas_restantes = max(24, int(diferencia_segundos // 3600))
            await notificar_recordatorio_cita(
                db=db,
                cita_id=cita.id_PK,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=fecha_str,
                hora=hora_str,
                horas_restantes=horas_restantes,
                doctor_usuario_id=doctor_uid,
                paciente_usuario_id=paciente_uid
            )

            if correo_paciente:
                asyncio.create_task(
                    notificar_correo_recordatorio(
                        destinatario=correo_paciente,
                        paciente_nombre=paciente_nombre,
                        doctor_nombre=doctor_nombre,
                        fecha=fecha_str,
                        hora=hora_str,
                        intervalo_texto="1 semana (7 días)",
                        motivo=motivo_str
                    )
                )

async def ciclo_recordatorios_background(intervalo_segundos: int = 60):
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
    global _tarea_recordatorios_activa
    _tarea_recordatorios_activa = False
