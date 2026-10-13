from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.cola import Cola
from app.schemas.cita import CitaCrear, CitaResponse, CitaReprogramar, CitaActualizar
from app.core.dependencies import get_current_user
from app.services.citas_calendar_service import (
    sincronizar_creacion_google_calendar,
    sincronizar_actualizacion_google_calendar,
    sincronizar_eliminacion_google_calendar
)
from app.services.calendar_service import has_valid_credentials
from app.services.citas_notification_service import (
    notificar_cita_creada,
    notificar_cita_reprogramada,
    notificar_cita_cancelada
)


router = APIRouter(
    prefix="/api/citas",
    tags=["Citas"]
)


def verificar_permiso_recepcion(usuario_actual: Usuario):
    """Valida que el usuario tenga privilegios de administrador o recepcionista."""
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o recepcionista pueden gestionar citas"
        )


@router.get("/mis-consultas")
def obtener_mis_consultas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Devuelve las citas asignadas al doctor autenticado."""
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los doctores pueden ver sus consultas"
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    doctor = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == usuario_actual.id_PK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes un perfil de doctor registrado"
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    citas = (
        db.query(Cita)
        .filter(Cita.doctor_id_FK == doctor.id_PK)
        .order_by(Cita.fecha.desc(), Cita.hora_inicio.desc())
        .all()
    )

    return citas


@router.get("/")
def obtener_citas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Obtiene la lista completa de citas ordenadas cronológicamente."""
    verificar_permiso_recepcion(usuario_actual)

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    citas = (
        db.query(Cita)
        .order_by(Cita.fecha, Cita.hora_inicio)
        .all()
    )

    return citas


@router.post(
    "/",
    response_model=CitaResponse,
    status_code=status.HTTP_201_CREATED
)
async def crear_cita(
    datos: CitaCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Registra una cita médica, la agrega a Google Calendar (CU-05, CU-12) y notifica por WebSockets."""
    verificar_permiso_recepcion(usuario_actual)

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    paciente = (
        db.query(Paciente)
        .filter(Paciente.id_PK == datos.paciente_id_FK)
        .first()
    )

    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El paciente no existe"
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id_PK == datos.doctor_id_FK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El doctor no existe"
        )

    paciente_nombre = f"{paciente.nombre} {paciente.apellido}"
    doctor_nombre = doctor.nombre
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if doctor.usuario_id_FK else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    # Priorizar la cuenta de Google Calendar del Doctor asignado; si no, la del creador
    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

    # Sincronización con Google Calendar API (Fase 2 -> CU-12)
    google_event_id = None
    if target_calendar_user:
        google_event_id = sincronizar_creacion_google_calendar(
            user_id=target_calendar_user,
            fecha=datos.fecha,
            hora_inicio=datos.hora_inicio,
            hora_fin=datos.hora_fin,
            paciente_nombre=paciente_nombre,
            doctor_nombre=doctor_nombre,
            motivo=datos.motivo
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    nueva_cita = Cita(
        paciente_id_FK=datos.paciente_id_FK,
        doctor_id_FK=datos.doctor_id_FK,
        fecha=datos.fecha,
        hora_inicio=datos.hora_inicio,
        hora_fin=datos.hora_fin,
        estado=datos.estado,
        motivo=datos.motivo,
        notas=datos.notas,
        creado_por=usuario_actual.id_PK,
        google_event_id=google_event_id
    )

    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)

    # Persistencia en BD y emisión reactiva por WebSocket
    await notificar_cita_creada(
        db=db,
        cita_id=nueva_cita.id_PK,
        paciente_nombre=paciente_nombre,
        doctor_nombre=doctor_nombre,
        fecha=str(nueva_cita.fecha),
        hora=nueva_cita.hora_inicio.strftime("%H:%M") if nueva_cita.hora_inicio else "",
        doctor_usuario_id=doctor.usuario_id_FK,
        creador_usuario_id=usuario_actual.id_PK,
        paciente_usuario_id=getattr(paciente, "usuario_id_FK", None)
    )

    return nueva_cita


@router.put("/{cita_id}", response_model=CitaResponse)
@router.put("/{cita_id}/reprogramar", response_model=CitaResponse)
async def reprogramar_cita(
    cita_id: int,
    datos: CitaReprogramar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Reprograma fecha y hora de una cita, actualiza Google Calendar (CU-07) y notifica por WebSockets."""
    verificar_permiso_recepcion(usuario_actual)

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
    doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

    paciente_nombre = f"{paciente.nombre} {paciente.apellido}" if paciente else f"Paciente #{cita.paciente_id_FK}"
    doctor_nombre = doctor.nombre if doctor else f"Doctor #{cita.doctor_id_FK}"
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if (doctor and doctor.usuario_id_FK) else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    cita.fecha = datos.fecha
    cita.hora_inicio = datos.hora_inicio
    cita.hora_fin = datos.hora_fin
    if datos.motivo is not None:
        cita.motivo = datos.motivo
    if datos.notas is not None:
        cita.notas = datos.notas

    # Priorizar la cuenta de Google Calendar del Doctor asignado; si no, la del creador
    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

    # Sincronización en Google Calendar al reprogramar (CU-07, CU-12)
    if target_calendar_user:
        nuevo_event_id = sincronizar_actualizacion_google_calendar(
            user_id=target_calendar_user,
            event_id=cita.google_event_id,
            fecha=cita.fecha,
            hora_inicio=cita.hora_inicio,
            hora_fin=cita.hora_fin,
            paciente_nombre=paciente_nombre,
            doctor_nombre=doctor_nombre,
            motivo=cita.motivo
        )
        if nuevo_event_id:
            cita.google_event_id = nuevo_event_id

    db.commit()
    db.refresh(cita)

    # Persistencia en BD y emisión reactiva por WebSocket
    await notificar_cita_reprogramada(
        db=db,
        cita_id=cita.id_PK,
        paciente_nombre=paciente_nombre,
        doctor_nombre=doctor_nombre,
        nueva_fecha=str(cita.fecha),
        nueva_hora=cita.hora_inicio.strftime("%H:%M") if cita.hora_inicio else "",
        doctor_usuario_id=doctor.usuario_id_FK if doctor else None,
        creador_usuario_id=usuario_actual.id_PK,
        paciente_usuario_id=getattr(paciente, "usuario_id_FK", None) if paciente else None
    )

    return cita


@router.delete("/{cita_id}", status_code=status.HTTP_200_OK)
async def eliminar_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Elimina o cancela una cita, sincronizando con Google Calendar (CU-08) y notificando vía WebSocket."""
    verificar_permiso_recepcion(usuario_actual)

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
    paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
    doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

    paciente_nombre = f"{paciente.nombre} {paciente.apellido}" if paciente else f"Paciente #{cita.paciente_id_FK}"
    doctor_nombre = doctor.nombre if doctor else f"Doctor #{cita.doctor_id_FK}"
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if (doctor and doctor.usuario_id_FK) else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    # Priorizar la cuenta de Google Calendar del Doctor asignado; si no, la del creador
    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

    # Eliminación de Google Calendar (CU-08)
    if cita.google_event_id and target_calendar_user:
        sincronizar_eliminacion_google_calendar(user_id=target_calendar_user, event_id=cita.google_event_id)

    try:
        # TODO: Reemplazar con la consulta a tu ORM (SQLAlchemy/Prisma)
        cola = db.query(Cola).filter(Cola.cita_id_FK == cita_id).first()
        if cola:
            db.delete(cola)
            db.flush()

        db.delete(cita)
        db.commit()

        # Notificación reactiva por WebSocket y persistencia en BD
        await notificar_cita_cancelada(
            db=db,
            cita_id=cita_id,
            paciente_nombre=paciente_nombre,
            doctor_nombre=doctor_nombre,
            doctor_usuario_id=doctor.usuario_id_FK if doctor else None,
            creador_usuario_id=usuario_actual.id_PK,
            paciente_usuario_id=getattr(paciente, "usuario_id_FK", None) if paciente else None
        )

        return {
            "mensaje": f"Cita #{cita_id} eliminada correctamente",
            "id_eliminado": cita_id,
            "turno_eliminado": cola.numero_cola if cola else None
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo eliminar la cita: {str(e)}"
        )


@router.post("/disparar-recordatorios", status_code=status.HTTP_200_OK)
async def disparar_recordatorios_manual(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Ejecuta inmediatamente la verificación de recordatorios de citas próximas (CU-11)."""
    from app.services.reminder_service import verificar_y_emitir_recordatorios
    await verificar_y_emitir_recordatorios(db)
    return {
        "status": "success",
        "mensaje": "Verificación de recordatorios de citas ejecutada correctamente."
    }