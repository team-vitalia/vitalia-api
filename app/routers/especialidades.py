
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.especialidad import Especialidad
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.doctor_especialidad import DoctorEspecialidad
from app.schemas.especialidad import (
    EspecialidadCrear,
    EspecialidadActualizar,
    EspecialidadResponse,
)


router = APIRouter(
    prefix="/api/especialidades",
    tags=["Especialidades"],
)


def exigir_administrador(usuario: Usuario):
    if usuario.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede gestionar especialidades",
        )


def validar_nombre(nombre: str) -> str:
    nombre_limpio = nombre.strip()

    if not nombre_limpio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre de la especialidad es obligatorio",
        )

    return nombre_limpio


def buscar_nombre_duplicado(db: Session, nombre: str, excluir_id: int | None = None):
    consulta = db.query(Especialidad).filter(
        func.lower(Especialidad.nombre) == nombre.lower()
    )

    if excluir_id is not None:
        consulta = consulta.filter(
            Especialidad.id_PK != excluir_id
        )

    return consulta.first()


# =========================================================
# CONSULTAR ESPECIALIDADES
# =========================================================

@router.get("/", response_model=list[EspecialidadResponse])
def obtener_especialidades(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el administrador, doctor o recepcionista "
                "pueden consultar las especialidades"
            ),
        )

    return (
        db.query(Especialidad)
        .filter(Especialidad.esta_activo.is_(True))
        .order_by(Especialidad.nombre)
        .all()
    )


# =========================================================
# AGREGAR ESPECIALIDAD
# =========================================================

@router.post(
    "/",
    response_model=EspecialidadResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_especialidad(
    datos: EspecialidadCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_administrador(usuario_actual)

    nombre = validar_nombre(datos.nombre)

    if buscar_nombre_duplicado(db, nombre):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una especialidad con ese nombre",
        )

    nueva = Especialidad(
        nombre=nombre,
        descripcion=datos.descripcion,
        codigo=datos.codigo,
        esta_activo=True,
    )

    try:
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        return nueva
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la especialidad",
        )

# =========================================================
# CREAR ESPECIALIDAD Y ASOCIARLA AL DOCTOR AUTENTICADO
# =========================================================

@router.post(
    "/para-mi-perfil",
    response_model=EspecialidadResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_especialidad_para_doctor(
    datos: EspecialidadCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    # Solo los doctores pueden crear especialidades desde su perfil.
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un doctor puede agregar especialidades a su perfil",
        )

    nombre = validar_nombre(datos.nombre)
    descripcion = (
        datos.descripcion.strip()
        if datos.descripcion and datos.descripcion.strip()
        else None
    )
    codigo = (
        datos.codigo.strip().upper()
        if datos.codigo and datos.codigo.strip()
        else None
    )

    if not descripcion or not codigo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre, la descripción y el código son obligatorios",
        )

    # Buscar el perfil del doctor autenticado.
    doctor = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == usuario_actual.id_PK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el perfil del doctor autenticado",
        )

    # Evitar nombres duplicados.
    existente = buscar_nombre_duplicado(db, nombre)

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una especialidad con ese nombre",
        )

    # Evitar códigos duplicados, ignorando mayúsculas y minúsculas.
    codigo_existente = (
        db.query(Especialidad)
        .filter(func.lower(Especialidad.codigo) == codigo.lower())
        .first()
    )

    if codigo_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una especialidad con ese código",
        )

    try:
        # 1. Guardar la especialidad.
        nueva = Especialidad(
            nombre=nombre,
            descripcion=descripcion,
            codigo=codigo,
            esta_activo=True,
        )

        db.add(nueva)
        db.flush()

        # 2. Crear la relación con el doctor.
        relacion = DoctorEspecialidad(
            doctor_id_FK=doctor.id_PK,
            especialidad_id_FK=nueva.id_PK,
        )

        db.add(relacion)

        # Confirmar ambas inserciones en una sola transacción.
        db.commit()
        db.refresh(nueva)

        return nueva

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No se pudo registrar la especialidad "
                "y asociarla al perfil del doctor"
            ),
        )

# =========================================================
# EDITAR ESPECIALIDAD
# =========================================================

@router.put("/{especialidad_id}", response_model=EspecialidadResponse)
def editar_especialidad(
    especialidad_id: int,
    datos: EspecialidadActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_administrador(usuario_actual)

    especialidad = (
        db.query(Especialidad)
        .filter(Especialidad.id_PK == especialidad_id)
        .first()
    )

    if not especialidad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La especialidad no existe",
        )

    nombre = validar_nombre(datos.nombre)

    if buscar_nombre_duplicado(db, nombre, excluir_id=especialidad_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe otra especialidad con ese nombre",
        )

    especialidad.nombre = nombre
    especialidad.descripcion = datos.descripcion
    especialidad.codigo = datos.codigo

    try:
        db.commit()
        db.refresh(especialidad)
        return especialidad
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar la especialidad",
        )



@router.get("/{especialidad_id}/doctores-asignados")
def verificar_doctores_asignados(
    especialidad_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_administrador(usuario_actual)

    especialidad = (
        db.query(Especialidad)
        .filter(Especialidad.id_PK == especialidad_id)
        .first()
    )

    if not especialidad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La especialidad no existe",
        )

    # Revisar la tabla intermedia
    relacion_intermedia = (
        db.query(DoctorEspecialidad.id_PK)
        .filter(
            DoctorEspecialidad.especialidad_id_FK == especialidad_id
        )
        .first()
    )

    # Revisar la columna antigua de doctores
    relacion_antigua = (
        db.query(Doctor.id_PK)
        .filter(Doctor.especialidad_id_FK == especialidad_id)
        .first()
    )

    tiene_doctores = (
        relacion_intermedia is not None
        or relacion_antigua is not None
    )

    return {
        "tiene_doctores": tiene_doctores,
        "mensaje": (
            "No se puede eliminar porque hay doctores asignados a esta especialidad."
            if tiene_doctores
            else "No hay doctores asignados a esta especialidad."
        ),
    }

# =========================================================
# ELIMINAR ESPECIALIDAD
# =========================================================

@router.delete("/{especialidad_id}")
def eliminar_especialidad(
    especialidad_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_administrador(usuario_actual)

    especialidad = (
        db.query(Especialidad)
        .filter(Especialidad.id_PK == especialidad_id)
        .first()
    )

    if not especialidad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La especialidad no existe",
        )

    # Verificar si hay algún doctor con esta especialidad
    doctor_asociado = (
        db.query(Doctor.id_PK)
        .filter(Doctor.especialidad_id_FK == especialidad_id)
        .first()
    )

    # Si existe al menos uno, impedir la eliminación
    if doctor_asociado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede eliminar esta especialidad porque "
                "está asignada a uno o más doctores. "
                "Reasigna la especialidad del doctor antes de eliminarla."
            ),
        )
        
        # Verificar la tabla intermedia
        relacion_intermedia = (
            db.query(DoctorEspecialidad.id_PK)
            .filter(
                DoctorEspecialidad.especialidad_id_FK == especialidad_id
            )
            .first()
        )

        # Verificar la columna antigua
        relacion_antigua = (
            db.query(Doctor.id_PK)
            .filter(Doctor.especialidad_id_FK == especialidad_id)
            .first()
        )

        # Impedir la eliminación si existe alguna relación
        if relacion_intermedia or relacion_antigua:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No se puede eliminar esta especialidad porque "
                    "está asignada a uno o más doctores. "
                    "Reasigna o desasigna la especialidad antes de eliminarla."
                ),
            )

    # Eliminar solo cuando ningún doctor la tenga asignada
    try:
        db.delete(especialidad)
        db.commit()

        return {
            "mensaje": "Especialidad eliminada correctamente"
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo eliminar la especialidad",
        )