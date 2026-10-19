import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.models.alergia import Alergia 
from app.models.alergia_paciente import AlergiaPaciente
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.cola import Cola
from app.schemas.cita import CitaCrear, CitaResponse, CitaReprogramar, CitaActualizar, CitaEstado
from app.models.equipamiento_sala import EquipamientoSala
from app.models.sala import Sala
from app.routers.doctor_salas import sala_valida_para_cita
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
from app.services.email_service import (
    notificar_correo_cita_creada,
    notificar_correo_cita_reprogramada
)

# --- ESQUEMAS Y CONSTANTES ---
class EstadoCitaSchema(BaseModel):
    nuevo_estado: str

class ReasignarCitaSchema(BaseModel):
    nuevo_doctor_id: int

# Variable movida aquí para evitar el error de sintaxis
ESTADOS_CITA = ("programada", "confirmada", "en_curso", "completada", "cancelada", "no_asistio")

router = APIRouter(
    prefix="/api/citas",
    tags=["Citas"]
)

def verificar_permiso_recepcion(usuario_actual: Usuario):
    if usuario_actual.rol_id_FK not in [1, 4, 5]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador, coordinador o recepcionista pueden gestionar citas"
        )

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

def validar_sala_equipo(
    db: Session,
    doctor_id: int,
    fecha,
    hora_inicio,
    hora_fin,
    sala_id,
    requiere_equipo: bool,
    equipo_id,
    accion_equipo,
    excluir_cita_id: int | None = None,
) -> str | None:
    """Valida sala/equipo de una cita. Devuelve la acción normalizada (o None)."""
    if hora_fin <= hora_inicio:
        raise HTTPException(status_code=422, detail="La hora de fin debe ser posterior a la de inicio")

    accion = (accion_equipo or "").strip() or None

    if sala_id is not None:
        sala = db.get(Sala, sala_id)
        if not sala:
            raise HTTPException(status_code=404, detail="La sala no existe")
        if (sala.estado or "disponible") in ("mantenimiento", "inactiva"):
            raise HTTPException(status_code=409, detail=f"La sala «{sala.nombre}» no está disponible")
        if not sala_valida_para_cita(db, doctor_id, sala_id, fecha, hora_inicio, hora_fin):
            raise HTTPException(
                status_code=409,
                detail="La sala no está asignada al doctor en ese día/horario",
            )
        choque = (
            db.query(Cita)
            .filter(
                Cita.sala_id_FK == sala_id,
                Cita.fecha == fecha,
                Cita.hora_inicio < hora_fin,
                Cita.hora_fin > hora_inicio,
                Cita.estado.notin_(["cancelada", "no_asistio"]) | Cita.estado.is_(None),
            )
        )
        if excluir_cita_id:
            choque = choque.filter(Cita.id_PK != excluir_cita_id)
        if choque.first():
            raise HTTPException(status_code=409, detail="La sala ya está ocupada en ese horario")

    if requiere_equipo:
        if sala_id is None:
            raise HTTPException(status_code=422, detail="Selecciona una sala para usar equipo")
        if equipo_id is None:
            raise HTTPException(status_code=422, detail="Selecciona el equipo a utilizar")
        if not accion:
            raise HTTPException(status_code=422, detail="Indica la acción a realizar con el equipo")
        equipo = db.get(EquipamientoSala, equipo_id)
        if not equipo or equipo.sala_id_FK != sala_id:
            raise HTTPException(status_code=400, detail="El equipo no pertenece a la sala seleccionada")
        if (equipo.estado or "operativo").lower() in ("mantenimiento", "averiado", "baja", "fuera_de_servicio"):
            raise HTTPException(status_code=409, detail="El equipo no está disponible")
        choque_eq = (
            db.query(Cita)
            .filter(
                Cita.equipo_id_FK == equipo_id,
                Cita.fecha == fecha,
                Cita.hora_inicio < hora_fin,
                Cita.hora_fin > hora_inicio,
                Cita.estado.notin_(["cancelada", "no_asistio"]) | Cita.estado.is_(None),
            )
        )
        if excluir_cita_id:
            choque_eq = choque_eq.filter(Cita.id_PK != excluir_cita_id)
        if choque_eq.first():
            raise HTTPException(status_code=409, detail="El equipo ya está reservado en ese horario")
    return accion

# ==============================================================================
# RUTAS GET (Las específicas primero, la dinámica al final)
# ==============================================================================

@router.get("/mis-consultas", response_model=list[CitaResponse])
def obtener_mis_consultas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los doctores pueden ver sus consultas"
        )

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

    citas = (
        db.query(Cita)
        .filter(Cita.doctor_id_FK == doctor.id_PK)
        .order_by(Cita.fecha.desc(), Cita.hora_inicio.desc())
        .all()
    )

    return citas


@router.get("/transferidas")
def obtener_citas_transferidas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(status_code=403, detail="Solo los doctores pueden ver esto")

    doctor_actual = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
    if not doctor_actual:
        raise HTTPException(status_code=404, detail="Perfil de doctor no encontrado")

    nombre_doctor = doctor_actual.usuario.nombre if doctor_actual.usuario else ""
    
    citas = (
        db.query(Cita)
        .filter(Cita.notas.contains(f"transferida por Dr. {nombre_doctor}"))
        .order_by(Cita.fecha.desc())
        .all()
    )

    resultado = []
    for cita in citas:
        nuevo_doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()
        nuevo_nombre = nuevo_doctor.usuario.nombre if nuevo_doctor and nuevo_doctor.usuario else "Desconocido"
        
        especialidad = "General"
        if nuevo_doctor and nuevo_doctor.especialidad:
            especialidad = nuevo_doctor.especialidad.nombre

        paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
        paciente_nombre = f"{paciente.nombre} {paciente.apellido}" if paciente else "Desconocido"

        resultado.append({
            "id_PK": cita.id_PK,
            "fecha": str(cita.fecha) if cita.fecha else None,
            "hora_inicio": str(cita.hora_inicio) if cita.hora_inicio else None,
            "hora_fin": str(cita.hora_fin) if cita.hora_fin else None,
            "estado": cita.estado,
            "motivo": cita.motivo,
            "notas": cita.notas,
            "paciente_nombre": paciente_nombre,
            "doctor_actual_nombre": nuevo_nombre,
            "doctor_actual_especialidad": especialidad
        })

    return resultado


@router.get("/mis-citas", response_model=list[CitaResponse])
def obtener_mis_citas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Citas del paciente autenticado (incluye si no se realizaron)."""
    if usuario_actual.rol_id_FK != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los pacientes pueden ver sus citas"
        )

    paciente = (
        db.query(Paciente)
        .filter(Paciente.usuario_id_FK == usuario_actual.id_PK)
        .first()
    )
    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes un perfil de paciente registrado"
        )

    return (
        db.query(Cita)
        .filter(Cita.paciente_id_FK == paciente.id_PK)
        .order_by(Cita.fecha.desc(), Cita.hora_inicio.desc())
        .all()
    )


@router.get("/", response_model=list[CitaResponse])
def obtener_citas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    citas = (
        db.query(Cita)
        .order_by(Cita.fecha, Cita.hora_inicio)
        .all()
    )

    return citas


@router.get("/{cita_id}")
def obtener_detalle_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los doctores pueden ver el detalle de sus consultas"
        )

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
    if not doctor or cita.doctor_id_FK != doctor.id_PK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta cita"
        )

    paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
    
    alergias_db = []
    if paciente:
        alergias_db = (
            db.query(AlergiaPaciente)
            .options(joinedload(AlergiaPaciente.alergia))
            .filter(AlergiaPaciente.paciente_id_FK == paciente.id_PK)
            .all()
        )

    return {
        "id_PK": cita.id_PK,
        "fecha": str(cita.fecha) if cita.fecha else None,
        "hora_inicio": str(cita.hora_inicio) if cita.hora_inicio else None,
        "hora_fin": str(cita.hora_fin) if cita.hora_fin else None,
        "estado": cita.estado,
        "motivo": cita.motivo,
        "notas": cita.notas,
        "paciente": {
            "id_PK": paciente.id_PK,
            "nombre": paciente.nombre,
            "apellido": paciente.apellido,
            "fecha_nacimiento": str(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else None,
            "telefono": paciente.telefono,
            "alergias": [
                {
                    "nombre": ap.alergia.nombre if ap.alergia else "Alergia desconocida",
                    "severidad": ap.severidad or (ap.alergia.severidad if ap.alergia else "No especificada")
                } for ap in alergias_db
            ]
        } if paciente else None
    }

# ==============================================================================
# RUTAS POST
# ==============================================================================

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
    verificar_permiso_recepcion(usuario_actual)

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

    accion_equipo = validar_sala_equipo(
        db, doctor.id_PK, datos.fecha, datos.hora_inicio, datos.hora_fin,
        datos.sala_id_FK, datos.requiere_equipo, datos.equipo_id_FK, datos.accion_equipo,
    )

    p_nom = getattr(paciente, "nombre", "") or ""
    p_ape = getattr(paciente, "apellido", "") or ""
    paciente_nombre = f"{p_nom} {p_ape}".strip() or f"Paciente {datos.paciente_id_FK}"
    doctor_nombre = getattr(doctor, "nombre", None) or f"Doctor {datos.doctor_id_FK}"
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if doctor.usuario_id_FK else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

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
        google_event_id=google_event_id,
        sala_id_FK=datos.sala_id_FK,
        requiere_equipo=bool(datos.requiere_equipo),
        equipo_id_FK=datos.equipo_id_FK if datos.requiere_equipo else None,
        accion_equipo=accion_equipo if datos.requiere_equipo else None,
    )

    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)

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

    correo_paciente = getattr(paciente, "correo_electronico", None)
    if not correo_paciente and paciente and getattr(paciente, "usuario_id_FK", None):
        usuario_paciente = db.query(Usuario).filter(Usuario.id_PK == paciente.usuario_id_FK).first()
        if usuario_paciente:
            correo_paciente = usuario_paciente.correo_electronico

    if correo_paciente:
        asyncio.create_task(
            notificar_correo_cita_creada(
                destinatario=correo_paciente,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                fecha=str(nueva_cita.fecha),
                hora_inicio=nueva_cita.hora_inicio.strftime("%H:%M") if nueva_cita.hora_inicio else "",
                hora_fin=nueva_cita.hora_fin.strftime("%H:%M") if nueva_cita.hora_fin else "",
                motivo=nueva_cita.motivo or "Consulta médica general"
            )
        )

    return nueva_cita


@router.post("/disparar-recordatorios", status_code=status.HTTP_200_OK)
async def disparar_recordatorios_manual(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    from app.services.reminder_service import verificar_y_emitir_recordatorios
    await verificar_y_emitir_recordatorios(db)
    return {
        "status": "success",
        "mensaje": "Verificación de recordatorios de citas ejecutada correctamente."
    }

# ==============================================================================
# RUTAS PUT
# ==============================================================================

@router.put("/{cita_id}/estado")
def cambiar_estado_cita(
    cita_id: int,
    nuevo_estado: str = Query(..., description="Nuevo estado de la cita"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    print(f"--> BACKEND: Recibida petición para terminar cita {cita_id} con estado {nuevo_estado}")
    
    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    if usuario_actual.rol_id_FK == 2:
        doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
        if not doctor or cita.doctor_id_FK != doctor.id_PK:
            raise HTTPException(status_code=403, detail="No puedes modificar esta cita")

    cita.estado = nuevo_estado
    
    # Agregar nota automática si se completa
    if nuevo_estado == "completada" or nuevo_estado == "atendida":
        nota_anterior = cita.notas or ""
        cita.notas = f"{nota_anterior}\n[Cita terminada el {date.today()}]".strip()
        
    db.commit()
    db.refresh(cita)
    
    print(f"--> BACKEND: Cita {cita_id} actualizada exitosamente a {nuevo_estado}")
    return {"mensaje": f"Cita actualizada a {nuevo_estado}", "cita": cita}


@router.put("/{cita_id}/reasignar")
def reasignar_cita(
    cita_id: int,
    nuevo_doctor_id: int = Query(..., description="ID del nuevo doctor"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    print(f"--> BACKEND: Recibida petición para reasignar cita {cita_id} al doctor {nuevo_doctor_id}")
    
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(status_code=403, detail="Solo los doctores pueden reasignar citas")

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    doctor_actual = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
    if not doctor_actual or cita.doctor_id_FK != doctor_actual.id_PK:
        raise HTTPException(status_code=403, detail="Solo puedes reasignar tus propias citas")

    nuevo_doctor = db.query(Doctor).filter(Doctor.id_PK == nuevo_doctor_id, Doctor.estado == "activo").first()
    if not nuevo_doctor:
        raise HTTPException(status_code=404, detail="El doctor seleccionado no existe o está inactivo")

    nombre_anterior = doctor_actual.usuario.nombre if doctor_actual.usuario else "Desconocido"
    nombre_nuevo = nuevo_doctor.usuario.nombre if nuevo_doctor.usuario else "Desconocido"
    
    nota_anterior = cita.notas or ""
    nueva_nota = f"{nota_anterior}\n[Cita transferida por Dr. {nombre_anterior} al Dr. {nombre_nuevo}]".strip()
    cita.notas = nueva_nota
    
    cita.doctor_id_FK = nuevo_doctor_id
    db.commit()
    db.refresh(cita)
    
    print(f"--> BACKEND: Cita {cita_id} reasignada exitosamente")
    return {"mensaje": "Cita reasignada correctamente", "cita": cita}


@router.put("/{cita_id}", response_model=CitaResponse)
@router.put("/{cita_id}/reprogramar", response_model=CitaResponse)
async def reprogramar_cita(
    cita_id: int,
    datos: CitaReprogramar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
    doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

    p_nom = getattr(paciente, "nombre", "") if paciente else ""
    p_ape = getattr(paciente, "apellido", "") if paciente else ""
    paciente_nombre = f"{p_nom} {p_ape}".strip() if (p_nom or p_ape) else f"Paciente {cita.paciente_id_FK}"
    doctor_nombre = getattr(doctor, "nombre", None) if doctor else f"Doctor {cita.doctor_id_FK}"
    if not doctor_nombre:
        doctor_nombre = f"Doctor {cita.doctor_id_FK}"
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if (doctor and doctor.usuario_id_FK) else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    campos = datos.model_fields_set
    sala_id = datos.sala_id_FK if "sala_id_FK" in campos else cita.sala_id_FK
    req_eq = datos.requiere_equipo if datos.requiere_equipo is not None else cita.requiere_equipo
    eq_id = datos.equipo_id_FK if "equipo_id_FK" in campos else cita.equipo_id_FK
    accion = datos.accion_equipo if "accion_equipo" in campos else cita.accion_equipo
    if sala_id is not None or req_eq:
        accion = validar_sala_equipo(
            db, cita.doctor_id_FK, datos.fecha, datos.hora_inicio, datos.hora_fin,
            sala_id, req_eq, eq_id, accion, excluir_cita_id=cita.id_PK,
        )
    cita.sala_id_FK = sala_id
    cita.requiere_equipo = bool(req_eq)
    cita.equipo_id_FK = eq_id if req_eq else None
    cita.accion_equipo = accion if req_eq else None

    cita.fecha = datos.fecha
    cita.hora_inicio = datos.hora_inicio
    cita.hora_fin = datos.hora_fin
    if datos.motivo is not None:
        cita.motivo = datos.motivo
    if datos.notas is not None:
        cita.notas = datos.notas

    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

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

    correo_paciente = getattr(paciente, "correo_electronico", None)
    if not correo_paciente and paciente and getattr(paciente, "usuario_id_FK", None):
        usuario_paciente = db.query(Usuario).filter(Usuario.id_PK == paciente.usuario_id_FK).first()
        if usuario_paciente:
            correo_paciente = usuario_paciente.correo_electronico

    if correo_paciente:
        asyncio.create_task(
            notificar_correo_cita_reprogramada(
                destinatario=correo_paciente,
                paciente_nombre=paciente_nombre,
                doctor_nombre=doctor_nombre,
                nueva_fecha=str(cita.fecha),
                nueva_hora_inicio=cita.hora_inicio.strftime("%H:%M") if cita.hora_inicio else "",
                nueva_hora_fin=cita.hora_fin.strftime("%H:%M") if cita.hora_fin else "",
                motivo=cita.motivo or "Consulta médica general"
            )
        )

    return cita


@router.patch("/{cita_id}/estado", response_model=CitaResponse)
async def cambiar_estado_cita_patch(
    cita_id: int,
    datos: CitaEstado,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Cambia el estado de la cita (p. ej. marcar «no_asistio» o «completada»)."""
    estado = datos.estado.strip().lower()
    if estado not in ESTADOS_CITA:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Usa: {', '.join(ESTADOS_CITA)}")

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="La cita no existe")

    if usuario_actual.rol_id_FK == 2:
        doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
        if not doctor or doctor.id_PK != cita.doctor_id_FK:
            raise HTTPException(status_code=403, detail="Solo puedes modificar tus propias citas")
    else:
        verificar_permiso_recepcion(usuario_actual)

    cita.estado = estado
    db.commit()
    db.refresh(cita)
    return cita

# ==============================================================================
# RUTAS DELETE
# ==============================================================================

@router.delete("/{cita_id}", status_code=status.HTTP_200_OK)
async def eliminar_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    paciente = db.query(Paciente).filter(Paciente.id_PK == cita.paciente_id_FK).first()
    doctor = db.query(Doctor).filter(Doctor.id_PK == cita.doctor_id_FK).first()

    p_nom = getattr(paciente, "nombre", "") if paciente else ""
    p_ape = getattr(paciente, "apellido", "") if paciente else ""
    paciente_nombre = f"{p_nom} {p_ape}".strip() if (p_nom or p_ape) else f"Paciente {cita.paciente_id_FK}"
    doctor_nombre = getattr(doctor, "nombre", None) if doctor else f"Doctor {cita.doctor_id_FK}"
    if not doctor_nombre:
        doctor_nombre = f"Doctor {cita.doctor_id_FK}"
    doctor_user_id = f"user_{doctor.usuario_id_FK}" if (doctor and doctor.usuario_id_FK) else None
    creador_user_id = f"user_{usuario_actual.id_PK}"

    target_calendar_user = None
    if doctor_user_id and has_valid_credentials(doctor_user_id):
        target_calendar_user = doctor_user_id
    elif has_valid_credentials(creador_user_id):
        target_calendar_user = creador_user_id

    if cita.google_event_id and target_calendar_user:
        sincronizar_eliminacion_google_calendar(user_id=target_calendar_user, event_id=cita.google_event_id)

    try:
        cola = db.query(Cola).filter(Cola.cita_id_FK == cita_id).first()
        if cola:
            db.delete(cola)
            db.flush()

        db.delete(cita)
        db.commit()

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
            "mensaje": f"Cita {cita_id} eliminada correctamente",
            "id_eliminado": cita_id,
            "turno_eliminado": cola.numero_cola if cola else None
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo eliminar la cita: {str(e)}"
        )