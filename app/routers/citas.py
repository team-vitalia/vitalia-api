from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.cola import Cola
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


@router.get("/mis-consultas")
def obtener_mis_consultas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Devuelve las citas del doctor que está logueado.
    Solo accesible para doctores (rol 2).
    """

    # Solo doctores
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los doctores pueden ver sus consultas"
        )

    # 1. Buscar el perfil del doctor
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

    # 2. Buscar las citas del doctor
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

@router.delete("/{cita_id}", status_code=status.HTTP_200_OK)
def eliminar_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Elimina una cita.
    Si tiene turno asociado, también elimina el turno (en cascada).
    """

    verificar_permiso_recepcion(usuario_actual)

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()

    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    try:
        # 1. Eliminar la cola asociada (si existe)
        cola = db.query(Cola).filter(Cola.cita_id_FK == cita_id).first()

        if cola:
            db.delete(cola)
            db.flush()  # Aseguramos que se elimine antes de la cita

        # 2. Eliminar la cita
        db.delete(cita)
        db.commit()

        return {
            "mensaje": f"Cita #{cita_id} eliminada correctamente",
            "id_eliminado": cita_id,
            "turno_eliminado": cola.numero_cola if cola else None
        }

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo eliminar la cita: {str(e)}"
        )