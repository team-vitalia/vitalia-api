from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.especialidad import Especialidad
from app.models.usuario import Usuario
from app.schemas.especialidad import (
    EspecialidadCrear,
    EspecialidadResponse
)
from app.core.dependencies import get_current_user


router = APIRouter(
    prefix="/api/especialidades",
    tags=["Especialidades"]
)


# =========================================================
# OBTENER ESPECIALIDADES
# =========================================================

@router.get(
    "/",
    response_model=list[EspecialidadResponse]
)
def obtener_especialidades(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    # Solo administrador y recepción pueden consultar
    # las especialidades.

    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el administrador o recepcionista "
                "pueden consultar las especialidades"
            )
        )

    especialidades = (
        db.query(Especialidad)
        .filter(
            Especialidad.esta_activo == True
        )
        .order_by(
            Especialidad.nombre
        )
        .all()
    )

    return especialidades


# =========================================================
# CREAR ESPECIALIDAD
# =========================================================

@router.post(
    "/",
    response_model=EspecialidadResponse,
    status_code=status.HTTP_201_CREATED
)
def crear_especialidad(
    datos: EspecialidadCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    # Solo administrador puede crear especialidades

    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el administrador puede "
                "crear especialidades"
            )
        )

    # Verificar si ya existe una especialidad
    # con el mismo nombre.

    especialidad_existente = (
        db.query(Especialidad)
        .filter(
            Especialidad.nombre == datos.nombre
        )
        .first()
    )

    if especialidad_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ya existe una especialidad "
                "con ese nombre"
            )
        )

    # Crear especialidad

    nueva_especialidad = Especialidad(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        codigo=datos.codigo,
        esta_activo=True
    )

    db.add(nueva_especialidad)
    db.commit()
    db.refresh(nueva_especialidad)

    return nueva_especialidad