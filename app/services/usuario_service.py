import logging

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.validaciones import componer_apellido
from app.models.doctor import Doctor
from app.models.doctor_especialidad import DoctorEspecialidad
from app.models.especialidad import Especialidad
from app.models.paciente import Paciente
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCrear

logger = logging.getLogger(__name__)

ROL_ADMIN = 1
ROL_DOCTOR = 2
ROL_PACIENTE = 3
ROL_RECEPCION = 4
ROL_COORDINADOR = 5

MSG_CORREO_DUPLICADO = "Ya existe un usuario con ese correo electrónico"
MSG_CURP_DUPLICADA = "Esta CURP ya está registrada"


def curp_ya_registrada(db: Session, curp: str, excluir_paciente_id: int | None = None) -> bool:
    consulta = db.query(Paciente).filter(Paciente.curp == curp)
    if excluir_paciente_id is not None:
        consulta = consulta.filter(Paciente.id_PK != excluir_paciente_id)
    return consulta.first() is not None


def _conflicto_desde_integridad(error: IntegrityError) -> HTTPException:
    texto = str(getattr(error, "orig", error)).lower()
    if "curp" in texto:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MSG_CURP_DUPLICADA)
    if "correo" in texto:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MSG_CORREO_DUPLICADO)
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Ya existe un registro con esos datos",
    )


def crear_usuario_con_perfil(
    db: Session,
    datos: UsuarioCrear,
    hash_contrasena: str,
    clinica_id: int | None = None,
) -> Usuario:
    target_clinica_id = (
        clinica_id
        if clinica_id is not None
        else (getattr(datos, "clinica_id_FK", None) or getattr(datos, "clinica_id", None) or 1)
    )

    usuario_existente = (
        db.query(Usuario)
        .filter(Usuario.correo_electronico == datos.correo_electronico)
        .first()
    )
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_CORREO_DUPLICADO,
        )

    rol = (
        db.query(Role)
        .filter(Role.id_PK == datos.rol_id_FK, Role.esta_activo == True)
        .first()
    )
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol seleccionado no existe o está inactivo",
        )

    try:
        if datos.rol_id_FK == ROL_PACIENTE:
            if not datos.apellido_paterno:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El apellido paterno es obligatorio para pacientes",
                )
            if not datos.curp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La CURP es obligatoria para pacientes",
                )
            if curp_ya_registrada(db, datos.curp):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=MSG_CURP_DUPLICADA,
                )

        nuevo_usuario = Usuario(
            clinica_id_FK=target_clinica_id,
            nombre=datos.nombre,
            apellido_paterno=datos.apellido_paterno,
            apellido_materno=datos.apellido_materno,
            correo_electronico=datos.correo_electronico,
            hash_contrasena=hash_contrasena,
            rol_id_FK=datos.rol_id_FK,
            estado="activo",
            telefono=datos.telefono,
            intentos_fallidos=0,
        )
        db.add(nuevo_usuario)

        db.flush()
        if datos.rol_id_FK == ROL_DOCTOR:
            especialidad_ids = list(datos.especialidad_ids)

            if datos.especialidad_id_FK is not None:
                if datos.especialidad_id_FK not in especialidad_ids:
                    especialidad_ids.append(datos.especialidad_id_FK)

            if len(especialidad_ids) != len(set(especialidad_ids)):
                raise HTTPException(
                    status_code=422,
                    detail="No puedes asignar una especialidad más de una vez",
                )

            if especialidad_ids:
                especialidades = (
                    db.query(Especialidad)
                    .filter(
                        Especialidad.id_PK.in_(especialidad_ids),
                        Especialidad.esta_activo.is_(True),
                    )
                    .all()
                )
                if len(especialidades) != len(especialidad_ids):
                    raise HTTPException(
                        status_code=400,
                        detail="Una o más especialidades no existen o están inactivas",
                    )

            licencia = datos.numero_licencia.strip() if datos.numero_licencia else None

            if licencia:
                duplicado = (
                    db.query(Doctor)
                    .filter(func.lower(Doctor.numero_licencia) == licencia.lower())
                    .first()
                )
                if duplicado:
                    raise HTTPException(
                        status_code=409,
                        detail="El número de licencia ya está registrado",
                    )

            nuevo_doctor = Doctor(
                usuario_id_FK=nuevo_usuario.id_PK,
                especialidad_id_FK=datos.especialidad_id_FK,
                numero_licencia=licencia,
                rfc=datos.rfc,
                estado="activo",
                costo_consulta=datos.costo_consulta,
            )
            db.add(nuevo_doctor)
            db.flush()

            for especialidad_id in especialidad_ids:
                db.add(
                    DoctorEspecialidad(
                        doctor_id_FK=nuevo_doctor.id_PK,
                        especialidad_id_FK=especialidad_id,
                    )
                )

        elif datos.rol_id_FK == ROL_PACIENTE:
            db.add(
                Paciente(
                    clinica_id_FK=target_clinica_id,
                    usuario_id_FK=nuevo_usuario.id_PK,
                    nombre=datos.nombre,
                    apellido=componer_apellido(datos.apellido_paterno, datos.apellido_materno),
                    apellido_paterno=datos.apellido_paterno,
                    apellido_materno=datos.apellido_materno,
                    curp=datos.curp,
                    fecha_nacimiento=datos.fecha_nacimiento,
                    genero=datos.genero,
                    telefono=datos.telefono,
                    direccion=datos.direccion,
                    correo_electronico=datos.correo_electronico,
                    estado="activo",
                )
            )
        db.commit()
        db.refresh(nuevo_usuario)
        return nuevo_usuario

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as error:
        db.rollback()
        raise _conflicto_desde_integridad(error)

    except Exception:
        db.rollback()
        logger.exception("Error al crear usuario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible crear el usuario. Inténtalo de nuevo.",
        )
