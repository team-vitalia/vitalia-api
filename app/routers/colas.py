from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from sqlalchemy import func

from app.database.connection import get_db
from app.models.cola import Cola
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.schemas.cola import ColaCrear, ColaActualizar, ColaResponse
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario


router = APIRouter(
    prefix="/api/colas",
    tags=["Colas"]
)


@router.post("/", response_model=ColaResponse, status_code=status.HTTP_201_CREATED)
def registrar_llegada(
    datos: ColaCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Registra la llegada de un paciente. Crea un registro en la tabla `colas`.
    Solo recepción (rol 4) y admin (rol 1) pueden usar esto.
    """

    # 1. Validar permisos
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo recepción o admin pueden registrar llegadas"
        )

    # 2. Verificar que la cita exista
    cita = db.query(Cita).filter(Cita.id_PK == datos.cita_id_FK).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cita no existe"
        )

    # 3. Verificar que la cita no tenga ya una cola registrada hoy
    hoy = datetime.now().date()
    cola_existente = (
        db.query(Cola)
        .filter(
            Cola.cita_id_FK == datos.cita_id_FK,
            func.date(Cola.hora_registro) == hoy
        )
        .first()
    )

    if cola_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cita ya tiene un turno registrado hoy"
        )

    try:
        # 4. Generar el número de cola (último del día + 1)
        ultimo_numero = (
            db.query(func.max(Cola.id_PK))
            .filter(func.date(Cola.hora_registro) == hoy)
            .scalar()
        )

        siguiente = 1 if ultimo_numero is None else ultimo_numero + 1
        numero_cola = f"{siguiente:03d}"  # Ej: 001, 002, 003

        # 5. Crear la cola
        nueva_cola = Cola(
            cita_id_FK=datos.cita_id_FK,
            paciente_id_FK=cita.paciente_id_FK if hasattr(cita, 'paciente_id_FK') else None,
            doctor_id_FK=cita.doctor_id_FK if hasattr(cita, 'doctor_id_FK') else None,
            numero_cola=numero_cola,
            estado="en_espera",
            hora_registro=datetime.now(),
            prioridad=datos.prioridad or "normal",
            hora_llamado=None,
            numero_consultorio=None
        )

        db.add(nueva_cola)
        db.commit()
        db.refresh(nueva_cola)

        return nueva_cola

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar llegada: {str(e)}"
        )


@router.get("/", response_model=List[ColaResponse])
def listar_colas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Devuelve todas las colas activas del día (en espera o llamadas).
    """

    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las colas"
        )

    hoy = datetime.now().date()

    colas = (
        db.query(Cola)
        .filter(
            func.date(Cola.hora_registro) == hoy
        )
        .order_by(Cola.id_PK)
        .all()
    )

    return colas


@router.patch("/{cola_id}", response_model=ColaResponse)
def actualizar_cola(
    cola_id: int,
    datos: ColaActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Actualiza el estado de una cola (ej. llamar al paciente).
    """

    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso"
        )

    cola = db.query(Cola).filter(Cola.id_PK == cola_id).first()
    if not cola:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cola no encontrada"
        )

    try:
        if datos.estado is not None:
            cola.estado = datos.estado
            if datos.estado == "llamado":
                cola.hora_llamado = datetime.now()

        if datos.numero_consultorio is not None:
            cola.numero_consultorio = datos.numero_consultorio

        db.commit()
        db.refresh(cola)
        return cola

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar: {str(e)}"
        )

@router.get("/atendidas", response_model=List[ColaResponse])
def listar_colas_atendidas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Devuelve las colas que ya fueron atendidas hoy.
    """

    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las colas atendidas"
        )

    hoy = datetime.now().date()

    colas = (
        db.query(Cola)
        .filter(
            func.date(Cola.hora_registro) == hoy,
            Cola.estado == "atendido"
        )
        .order_by(Cola.id_PK.desc())
        .all()
    )

    return colas