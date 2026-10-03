from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.schemas.cita import CitaCrear, CitaResponse
from app.core.dependencies import get_current_user


router = APIRouter(
    prefix="/api/citas",
    tags=["Citas"]
)


def verificar_permiso_recepcion(
    usuario_actual: Usuario
):
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o recepcionista pueden gestionar citas"
        )


@router.get("/")
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


@router.post(
    "/",
    response_model=CitaResponse,
    status_code=status.HTTP_201_CREATED
)
def crear_cita(
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

    nueva_cita = Cita(
        paciente_id_FK=datos.paciente_id_FK,
        doctor_id_FK=datos.doctor_id_FK,
        fecha=datos.fecha,
        hora_inicio=datos.hora_inicio,
        hora_fin=datos.hora_fin,
        estado=datos.estado,
        motivo=datos.motivo,
        notas=datos.notas,
        creado_por=usuario_actual.id_PK
    )

    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)

    return nueva_cita