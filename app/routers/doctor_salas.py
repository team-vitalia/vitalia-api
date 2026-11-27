from datetime import time

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.horarios_sala import cubre, se_traslapan
from app.database.connection import get_db
from app.models.doctor import Doctor
from app.models.doctor_sala import DoctorSala
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.schemas.doctor_sala import (
    AsignacionCalendarioOut,
    AsignacionesSalas,
    AsignacionNueva,
    AsignacionSalaOut,
    ValidacionAsignacionOut,
)
from app.services.asignacion_salas_service import AsignacionSalasService

router = APIRouter(prefix="/api/doctor-salas", tags=["Salas de doctores"])

ROLES_GESTION = (1, 5)          # Administrador, Coordinador
ROLES_CONSULTA = (1, 2, 4, 5)   # + Doctor, Recepcionista


def _out(a: DoctorSala) -> AsignacionSalaOut:
    s = a.sala
    return AsignacionSalaOut(
        id_PK=a.id_PK,
        sala_id_FK=a.sala_id_FK,
        dia_semana=a.dia_semana,
        hora_inicio=a.hora_inicio,
        hora_fin=a.hora_fin,
        sala_nombre=s.nombre if s else None,
        sala_tipo=s.tipo if s else None,
        sala_piso=s.piso if s else None,
        sala_estado=s.estado if s else None,
    )


def _listar(db: Session, doctor_id: int) -> list[AsignacionSalaOut]:
    filas = (
        db.query(DoctorSala)
        .filter(DoctorSala.doctor_id_FK == doctor_id)
        .order_by(DoctorSala.sala_id_FK, DoctorSala.dia_semana, DoctorSala.hora_inicio)
        .all()
    )
    return [_out(f) for f in filas]


@router.get("/mis-salas", response_model=list[AsignacionSalaOut])
def mis_salas(
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    if actual.rol_id_FK != 2:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo los doctores tienen salas asignadas")
    doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == actual.id_PK).first()
    if not doctor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tienes un perfil de doctor registrado")
    return _listar(db, doctor.id_PK)


@router.get("/doctor/{doctor_id}", response_model=list[AsignacionSalaOut])
def salas_de_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    if actual.rol_id_FK not in ROLES_CONSULTA:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
    return _listar(db, doctor_id)


@router.put("/doctor/{doctor_id}", response_model=list[AsignacionSalaOut])
def asignar_salas(
    doctor_id: int,
    datos: AsignacionesSalas,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    """Reemplaza todas las asignaciones de salas/horarios del doctor."""
    if actual.rol_id_FK not in ROLES_GESTION:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo el administrador o coordinador pueden asignar salas",
        )
    if not db.get(Doctor, doctor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El doctor no existe")

    ids = {a.sala_id_FK for a in datos.asignaciones}
    if ids:
        existentes = {r[0] for r in db.query(Sala.id_PK).filter(Sala.id_PK.in_(ids)).all()}
        if existentes != ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Una o más salas no existen")

    # Evitar horarios traslapados del mismo doctor (considera turnos que cruzan la medianoche)
    lista = datos.asignaciones
    for i, a in enumerate(lista):
        for b in lista[i + 1:]:
            if se_traslapan(a.dia_semana, a.hora_inicio, a.hora_fin, b.dia_semana, b.hora_inicio, b.hora_fin):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "El doctor tiene horarios de sala traslapados",
                )

    # Una sala no puede quedar con dos doctores en el mismo horario
    servicio = AsignacionSalasService(db, clinica_id=getattr(actual, "clinica_id_FK", None))
    for a in datos.asignaciones:
        choques = servicio.conflictos_sala_otros(doctor_id, a.sala_id_FK, a.dia_semana, a.hora_inicio, a.hora_fin)
        if choques:
            raise HTTPException(status.HTTP_409_CONFLICT, choques[0].mensaje)

    db.query(DoctorSala).filter(DoctorSala.doctor_id_FK == doctor_id).delete()
    for a in datos.asignaciones:
        db.add(
            DoctorSala(
                doctor_id_FK=doctor_id,
                sala_id_FK=a.sala_id_FK,
                dia_semana=a.dia_semana,
                hora_inicio=a.hora_inicio,
                hora_fin=a.hora_fin,
            )
        )
    db.commit()
    return _listar(db, doctor_id)


# ---------------------------------------------------------------------------
#  Calendario de uso de salas: asignar / mover / quitar un bloque (doctor + sala + día + horario)
# ---------------------------------------------------------------------------
def _servicio(db: Session, actual: Usuario) -> AsignacionSalasService:
    return AsignacionSalasService(db, clinica_id=getattr(actual, "clinica_id_FK", None))


def _exigir_gestion(actual: Usuario) -> None:
    if actual.rol_id_FK not in ROLES_GESTION:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el administrador o coordinador pueden asignar salas")


@router.get("/calendario", response_model=list[AsignacionCalendarioOut])
def calendario(
    sala_id: Optional[int] = Query(None),
    doctor_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    """Todos los bloques de uso de salas de la clínica (filtrables por sala o por doctor)."""
    if actual.rol_id_FK not in ROLES_CONSULTA:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
    return _servicio(db, actual).calendario(sala_id=sala_id, doctor_id=doctor_id)


@router.post("/asignaciones/validar", response_model=ValidacionAsignacionOut)
def validar_asignacion(
    datos: AsignacionNueva,
    excluir_id: Optional[int] = Query(None, description="Bloque que se está moviendo (se ignora al validar)"),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    """Comprueba, sin guardar, si el doctor y la sala están libres en ese horario."""
    _exigir_gestion(actual)
    conflictos = _servicio(db, actual).validar(datos, excluir_id=excluir_id)
    return ValidacionAsignacionOut(valido=not conflictos, conflictos=conflictos)


@router.post("/asignaciones", status_code=status.HTTP_201_CREATED)
async def crear_asignacion(
    datos: AsignacionNueva,
    request: Request,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    """Asigna una sala a un doctor en un horario y (opcionalmente) le avisa."""
    _exigir_gestion(actual)
    fila, avisado = await _servicio(db, actual).crear(datos, actual, request)
    return {"id_PK": fila.id_PK, "doctor_notificado": avisado}


@router.put("/asignaciones/{asignacion_id}")
async def mover_asignacion(
    asignacion_id: int,
    datos: AsignacionNueva,
    request: Request,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    """Cambia el doctor, la sala, el día o el horario de un bloque ya asignado."""
    _exigir_gestion(actual)
    resultado = await _servicio(db, actual).actualizar(asignacion_id, datos, actual, request)
    if resultado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La asignación no existe")
    fila, avisado = resultado
    return {"id_PK": fila.id_PK, "doctor_notificado": avisado}


@router.delete("/asignaciones/{asignacion_id}")
async def quitar_asignacion(
    asignacion_id: int,
    request: Request,
    notificar: bool = Query(True),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(get_current_user),
):
    _exigir_gestion(actual)
    ok, avisado = await _servicio(db, actual).eliminar(asignacion_id, notificar, actual, request)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La asignación no existe")
    return {"eliminada": True, "doctor_notificado": avisado}


def sala_valida_para_cita(db: Session, doctor_id: int, sala_id: int, fecha, h_ini: time, h_fin: time) -> bool:
    """True si la sala está asignada al doctor y la cita cae dentro de un horario asignado."""
    filas = (
        db.query(DoctorSala)
        .filter(DoctorSala.doctor_id_FK == doctor_id, DoctorSala.sala_id_FK == sala_id)
        .all()
    )
    # Un turno nocturno (23:00 → 04:00) también cubre la madrugada del día siguiente.
    return any(cubre(f.dia_semana, f.hora_inicio, f.hora_fin, fecha.weekday(), h_ini, h_fin) for f in filas)
