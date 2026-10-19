from datetime import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.doctor import Doctor
from app.models.doctor_sala import DoctorSala
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.schemas.doctor_sala import AsignacionesSalas, AsignacionSalaOut

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

    # Evitar horarios traslapados del mismo doctor en el mismo día
    por_dia: dict[int | None, list] = {}
    for a in datos.asignaciones:
        por_dia.setdefault(a.dia_semana, []).append(a)
    for dia, lista in por_dia.items():
        todos = lista + (por_dia.get(None, []) if dia is not None else [])
        todos = sorted(todos, key=lambda x: x.hora_inicio)
        for ant, sig in zip(todos, todos[1:]):
            if sig.hora_inicio < ant.hora_fin:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "El doctor tiene horarios de sala traslapados",
                )

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


def sala_valida_para_cita(db: Session, doctor_id: int, sala_id: int, fecha, h_ini: time, h_fin: time) -> bool:
    """True si la sala está asignada al doctor y la cita cae dentro de un horario asignado."""
    filas = (
        db.query(DoctorSala)
        .filter(DoctorSala.doctor_id_FK == doctor_id, DoctorSala.sala_id_FK == sala_id)
        .all()
    )
    for f in filas:
        if f.dia_semana is not None and f.dia_semana != fecha.weekday():
            continue
        if f.hora_inicio and h_ini < f.hora_inicio:
            continue
        if f.hora_fin and h_fin > f.hora_fin:
            continue
        return True
    return False
