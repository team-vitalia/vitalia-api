from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.paciente import PacienteCrear, PacienteResponse
from app.core.dependencies import get_current_user


router = APIRouter(
    prefix="/api/pacientes",
    tags=["Pacientes"]
)


def verificar_permiso_recepcion(
    usuario_actual: Usuario
):
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o recepcionista pueden gestionar pacientes"
        )


@router.get("/")
def obtener_pacientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    pacientes = (
        db.query(Paciente)
        .order_by(Paciente.id_PK)
        .all()
    )

    return pacientes


@router.post(
    "/",
    response_model=PacienteResponse,
    status_code=status.HTTP_201_CREATED
)
def crear_paciente(
    datos: PacienteCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    paciente = Paciente(
        nombre=datos.nombre,
        apellido=datos.apellido,
        fecha_nacimiento=datos.fecha_nacimiento,
        genero=datos.genero,
        telefono=datos.telefono,
        direccion=datos.direccion,
        correo_electronico=datos.correo_electronico,
        estado="activo"
    )

    db.add(paciente)
    db.commit()
    db.refresh(paciente)

    return paciente