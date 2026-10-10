
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.especialidad import Especialidad
from app.models.doctor_especialidad import DoctorEspecialidad
from app.schemas.doctor import (
    DoctorCrear,
    DoctorActualizarPerfil,
    DoctorActualizarAdmin,
)

router = APIRouter(prefix="/api/doctores", tags=["Doctores"])


def exigir_administrador(usuario: Usuario):
    if usuario.rol_id_FK != 1:
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador puede gestionar perfiles de médicos"
        )


def exigir_medico(usuario: Usuario):
    if usuario.rol_id_FK != 2:
        raise HTTPException(
            status_code=403,
            detail="Esta operación está disponible para médicos"
        )


def validar_especialidades(db: Session, ids: list[int]):
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=422,
            detail="No puedes asignar una especialidad más de una vez"
        )

    if not ids:
        return []

    especialidades = (
        db.query(Especialidad)
        .filter(
            Especialidad.id_PK.in_(ids),
            Especialidad.esta_activo.is_(True)
        )
        .all()
    )

    if len(especialidades) != len(ids):
        raise HTTPException(
            status_code=400,
            detail="Una o más especialidades no existen o están inactivas"
        )

    return especialidades


def validar_licencia(
    db: Session,
    licencia: str | None,
    excluir_doctor_id: int | None = None
):
    if licencia is None:
        return None

    licencia = licencia.strip()

    if not licencia:
        return None

    consulta = db.query(Doctor).filter(
        func.lower(Doctor.numero_licencia) == licencia.lower()
    )

    if excluir_doctor_id is not None:
        consulta = consulta.filter(
            Doctor.id_PK != excluir_doctor_id
        )

    if consulta.first():
        raise HTTPException(
            status_code=409,
            detail="El número de licencia ya está registrado"
        )

    return licencia


def guardar_especialidades(
    db: Session,
    doctor: Doctor,
    especialidad_ids: list[int]
):
    validar_especialidades(db, especialidad_ids)

    db.query(DoctorEspecialidad).filter(
        DoctorEspecialidad.doctor_id_FK == doctor.id_PK
    ).delete(synchronize_session=False)

    for especialidad_id in especialidad_ids:
        db.add(
            DoctorEspecialidad(
                doctor_id_FK=doctor.id_PK,
                especialidad_id_FK=especialidad_id
            )
        )


def serializar_doctor(db: Session, doctor: Doctor):
    asignadas = (
        db.query(Especialidad)
        .join(
            DoctorEspecialidad,
            DoctorEspecialidad.especialidad_id_FK == Especialidad.id_PK
        )
        .filter(
            DoctorEspecialidad.doctor_id_FK == doctor.id_PK
        )
        .order_by(Especialidad.nombre)
        .all()
    )

    # Compatibilidad con registros antiguos que solo tienen
    # especialidad_id_FK y aún no usan la tabla intermedia.
    if not asignadas and doctor.especialidad:
        asignadas = [doctor.especialidad]

    return {
        "id_PK": doctor.id_PK,
        "usuario_id_FK": doctor.usuario_id_FK,
        "nombre": doctor.usuario.nombre if doctor.usuario else "Sin nombre",
        "correo_electronico": (
            doctor.usuario.correo_electronico if doctor.usuario else None
        ),
        "numero_licencia": doctor.numero_licencia,
        "estado": doctor.estado,
        "costo_consulta": (
            float(doctor.costo_consulta)
            if doctor.costo_consulta is not None else None
        ),
        "especialidades": [
            {
                "id_PK": especialidad.id_PK,
                "nombre": especialidad.nombre
            }
            for especialidad in asignadas
        ]
    }


@router.get("/")
def obtener_doctores(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 4]:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para consultar la lista de médicos"
        )

    doctores = (
        db.query(Doctor)
        .options(
            joinedload(Doctor.usuario),
            joinedload(Doctor.especialidad)
        )
        .filter(Doctor.estado == "activo")
        .order_by(Doctor.id_PK)
        .all()
    )

    return [serializar_doctor(db, doctor) for doctor in doctores]


@router.get("/perfil")
def obtener_mi_perfil(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_medico(usuario_actual)

    doctor = (
        db.query(Doctor)
        .options(
            joinedload(Doctor.usuario),
            joinedload(Doctor.especialidad)
        )
        .filter(Doctor.usuario_id_FK == usuario_actual.id_PK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Tu usuario todavía no tiene un perfil de médico"
        )

    return serializar_doctor(db, doctor)


@router.put("/perfil")
def actualizar_mi_perfil(
    datos: DoctorActualizarPerfil,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_medico(usuario_actual)

    doctor = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == usuario_actual.id_PK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Tu usuario todavía no tiene un perfil de médico"
        )

    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(
            status_code=422,
            detail="No se recibieron cambios"
        )

    try:
        if "numero_licencia" in cambios:
            licencia = cambios["numero_licencia"]
            doctor.numero_licencia = validar_licencia(
                db, licencia, doctor.id_PK
            )

        if "costo_consulta" in cambios:
            doctor.costo_consulta = cambios["costo_consulta"]

        if "especialidad_ids" in cambios:
            ids = cambios["especialidad_ids"]

            if ids is None:
                raise HTTPException(
                    status_code=422,
                    detail="La lista de especialidades no puede ser nula"
                )

            guardar_especialidades(db, doctor, ids)

        db.commit()
        db.refresh(doctor)

        return {
            "mensaje": "Tu perfil profesional se actualizó correctamente",
            "doctor": serializar_doctor(db, doctor)
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible actualizar tu perfil profesional"
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_doctor(
    datos: DoctorCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_administrador(usuario_actual)

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id_PK == datos.usuario_id_FK)
        .first()
    )

    if not usuario:
        raise HTTPException(status_code=404, detail="El usuario no existe")

    if usuario.rol_id_FK != 2:
        raise HTTPException(
            status_code=400,
            detail="El usuario seleccionado no tiene el rol de médico"
        )

    if db.query(Doctor).filter(
        Doctor.usuario_id_FK == usuario.id_PK
    ).first():
        raise HTTPException(
            status_code=409,
            detail="Este usuario ya tiene un perfil de médico"
        )

    ids = list(datos.especialidad_ids)

    if datos.especialidad_id_FK is not None:
        if datos.especialidad_id_FK not in ids:
            ids.append(datos.especialidad_id_FK)

    try:
        validar_especialidades(db, ids)

        nuevo_doctor = Doctor(
            usuario_id_FK=usuario.id_PK,
            especialidad_id_FK=datos.especialidad_id_FK,
            numero_licencia=validar_licencia(
                db, datos.numero_licencia
            ),
            estado=datos.estado,
            costo_consulta=datos.costo_consulta
        )

        db.add(nuevo_doctor)
        db.flush()

        guardar_especialidades(db, nuevo_doctor, ids)

        db.commit()
        db.refresh(nuevo_doctor)

        return {
            "mensaje": "Doctor registrado correctamente",
            "doctor": serializar_doctor(db, nuevo_doctor)
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible registrar al médico"
        )


@router.put("/{doctor_id}")
def actualizar_doctor_admin(
    doctor_id: int,
    datos: DoctorActualizarAdmin,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_administrador(usuario_actual)

    doctor = (
        db.query(Doctor)
        .options(
            joinedload(Doctor.usuario),
            joinedload(Doctor.especialidad)
        )
        .filter(Doctor.id_PK == doctor_id)
        .first()
    )

    if not doctor:
        raise HTTPException(status_code=404, detail="El médico no existe")

    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(
            status_code=422,
            detail="No se recibieron cambios"
        )

    if "estado" in cambios:
        if cambios["estado"] not in ["activo", "inactivo"]:
            raise HTTPException(
                status_code=422,
                detail="El estado debe ser activo o inactivo"
            )

    try:
        if "numero_licencia" in cambios:
            doctor.numero_licencia = validar_licencia(
                db, cambios["numero_licencia"], doctor.id_PK
            )

        if "costo_consulta" in cambios:
            doctor.costo_consulta = cambios["costo_consulta"]

        if "estado" in cambios:
            doctor.estado = cambios["estado"]

        if "especialidad_ids" in cambios:
            ids = cambios["especialidad_ids"]

            if ids is None:
                raise HTTPException(
                    status_code=422,
                    detail="La lista de especialidades no puede ser nula"
                )

            guardar_especialidades(db, doctor, ids)

        db.commit()
        db.refresh(doctor)

        return {
            "mensaje": "Perfil del médico actualizado correctamente",
            "doctor": serializar_doctor(db, doctor)
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible actualizar el perfil del médico"
        )