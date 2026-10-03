from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.especialidad import Especialidad
from app.schemas.doctor import DoctorCrear
from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/api/doctores",
    tags=["Doctores"]
)


def verificar_permiso_recepcion(usuario_actual: Usuario):
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o recepcionista pueden gestionar doctores"
        )


@router.get("/")
def obtener_doctores(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    doctores = (
        db.query(Doctor)
        .join(Usuario, Doctor.usuario_id_FK == Usuario.id_PK)
        .outerjoin(Especialidad, Doctor.especialidad_id_FK == Especialidad.id_PK)
        .filter(Doctor.estado == "activo")
        .all()
    )

    resultado = []

    for doctor in doctores:
        resultado.append({
            "id_PK": doctor.id_PK,
            "nombre": doctor.usuario.nombre if doctor.usuario else "Sin nombre",
            "especialidad": (
                doctor.especialidad.nombre
                if doctor.especialidad
                else "Sin especialidad"
            ),
            "estado": doctor.estado
        })

    return resultado


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_doctor(
    datos: DoctorCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    # Verificar que exista el usuario
    usuario = (
        db.query(Usuario)
        .filter(Usuario.id_PK == datos.usuario_id_FK)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )

    # Verificar que el usuario no sea ya doctor
    doctor_existente = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == datos.usuario_id_FK)
        .first()
    )

    if doctor_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este usuario ya está registrado como doctor"
        )

    # Verificar especialidad si se proporcionó
    if datos.especialidad_id_FK is not None:
        especialidad = (
            db.query(Especialidad)
            .filter(
                Especialidad.id_PK == datos.especialidad_id_FK
            )
            .first()
        )

        if not especialidad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La especialidad no existe"
            )

    nuevo_doctor = Doctor(
        usuario_id_FK=datos.usuario_id_FK,
        especialidad_id_FK=datos.especialidad_id_FK,
        numero_licencia=datos.numero_licencia,
        estado=datos.estado,
        costo_consulta=datos.costo_consulta
    )

    db.add(nuevo_doctor)
    db.commit()
    db.refresh(nuevo_doctor)

    return {
        "mensaje": "Doctor registrado correctamente",
        "doctor": {
            "id_PK": nuevo_doctor.id_PK,
            "usuario_id_FK": nuevo_doctor.usuario_id_FK,
            "especialidad_id_FK": nuevo_doctor.especialidad_id_FK,
            "numero_licencia": nuevo_doctor.numero_licencia,
            "estado": nuevo_doctor.estado,
            "costo_consulta": nuevo_doctor.costo_consulta
        }
    }