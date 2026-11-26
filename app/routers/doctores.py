from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import uuid4
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.models.especialidad import Especialidad
from app.models.doctor_especialidad import DoctorEspecialidad
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.schemas.doctor import (
    DoctorCrear,
    DoctorActualizarPerfil,
    DoctorActualizarAdmin,
)

router = APIRouter(prefix="/api/doctores", tags=["Doctores"])


def exigir_administrador(usuario: Usuario):
    if usuario.rol_id_FK not in [1, 5]:
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador o coordinador pueden gestionar perfiles de médicos"
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
    """
    Actualiza las especialidades del doctor sin eliminar
    los datos adicionales de las especialidades que conserva.
    """
    validar_especialidades(db, especialidad_ids)

    existentes = (
        db.query(DoctorEspecialidad)
        .filter(
            DoctorEspecialidad.doctor_id_FK == doctor.id_PK
        )
        .all()
    )

    # Relacionar cada especialidad con su registro intermedio.
    por_id = {
        asignacion.especialidad_id_FK: asignacion
        for asignacion in existentes
    }

    ids_deseados = set(especialidad_ids)

    # Eliminar únicamente las especialidades que ya no fueron seleccionadas.
    for especialidad_id, asignacion in por_id.items():
        if especialidad_id not in ids_deseados:
            db.delete(asignacion)

    # Crear únicamente las nuevas asignaciones.
    for especialidad_id in ids_deseados:
        if especialidad_id not in por_id:
            db.add(
                DoctorEspecialidad(
                    doctor_id_FK=doctor.id_PK,
                    especialidad_id_FK=especialidad_id
                )
            )

    db.flush()

def serializar_doctor(db: Session, doctor: Doctor):
    asignaciones = (
        db.query(DoctorEspecialidad)
        .join(Especialidad, DoctorEspecialidad.especialidad_id_FK == Especialidad.id_PK)
        .filter(DoctorEspecialidad.doctor_id_FK == doctor.id_PK)
        .order_by(Especialidad.nombre)
        .all()
    )
    if not asignaciones and doctor.especialidad:
        especialidades = [{
            "id_PK": doctor.especialidad.id_PK,
            "nombre": doctor.especialidad.nombre,
            "cedula_profesional": None,
            "documento_validez": None,
        }]
    else:
        especialidades = [{
            "id_PK": a.especialidad.id_PK,
            "nombre": a.especialidad.nombre,
            "cedula_profesional": a.cedula_profesional,
            "documento_validez": a.documento_validez,
        } for a in asignaciones]

    usuario = doctor.usuario
    return {
        "id_PK": doctor.id_PK,
        "usuario_id_FK": doctor.usuario_id_FK,
        "nombre": usuario.nombre if usuario else "Sin nombre",
        "apellido_paterno": usuario.apellido_paterno if usuario else None,
        "apellido_materno": usuario.apellido_materno if usuario else None,
        "correo_electronico": usuario.correo_electronico if usuario else None,
        "estado": doctor.estado,
        "estado_usuario": usuario.estado if usuario else None,
        "numero_licencia": doctor.numero_licencia,
        "rfc": doctor.rfc,
        "costo_consulta": float(doctor.costo_consulta) if doctor.costo_consulta is not None else None,
        "especialidades": especialidades,
    }


@router.get("/")
def obtener_doctores(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 4, 5]:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para consultar la lista de médicos"
        )

    query = (
        db.query(Doctor)
        .join(Doctor.usuario)
        .options(
            joinedload(Doctor.usuario),
            joinedload(Doctor.especialidad)
        )
        .filter(Doctor.estado == "activo")
    )
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None:
        query = query.filter(Usuario.clinica_id_FK == clinica_id)
    doctores = query.order_by(Doctor.id_PK).all()

    return [serializar_doctor(db, doctor) for doctor in doctores]


@router.get("/perfil")
def obtener_mi_perfil(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_medico(usuario_actual)

    doctor = (
        db.query(Doctor)
        .join(Doctor.usuario)
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
        .filter(
            Doctor.usuario_id_FK == usuario_actual.id_PK
        )
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
        # -----------------------------------------
        # 1. ACTUALIZAR NÚMERO DE LICENCIA
        # -----------------------------------------
        if "numero_licencia" in cambios:
            doctor.numero_licencia = validar_licencia(
                db,
                cambios["numero_licencia"],
                doctor.id_PK
            )

        # -----------------------------------------
        # 2. ACTUALIZAR COSTO DE CONSULTA
        # -----------------------------------------
        if "costo_consulta" in cambios:
            doctor.costo_consulta = cambios["costo_consulta"]

        # -----------------------------------------
        # 3. ACTUALIZAR ESPECIALIDADES ASIGNADAS
        # -----------------------------------------
        if "especialidad_ids" in cambios:
            ids = cambios["especialidad_ids"]

            if ids is None:
                raise HTTPException(
                    status_code=422,
                    detail="La lista de especialidades no puede ser nula"
                )

            # Valida que existan y estén activas.
            validar_especialidades(db, ids)

            # Actualiza las relaciones sin perder cédulas ni documentos.
            guardar_especialidades(
                db,
                doctor,
                ids
            )

        # -----------------------------------------
        # 4. ACTUALIZAR DATOS POR ESPECIALIDAD
        # -----------------------------------------
        if (
            "especialidades" in cambios
            and cambios["especialidades"] is not None
        ):
            detalles = cambios["especialidades"]

            ids_detalle = [
                item["id_PK"]
                for item in detalles
            ]

            # Evitar especialidades repetidas.
            if len(ids_detalle) != len(set(ids_detalle)):
                raise HTTPException(
                    status_code=422,
                    detail="Hay especialidades duplicadas."
                )

            # Obtener las especialidades que pertenecen al doctor.
            asignaciones = (
                db.query(DoctorEspecialidad)
                .filter(
                    DoctorEspecialidad.doctor_id_FK == doctor.id_PK
                )
                .all()
            )

            por_id = {
                asignacion.especialidad_id_FK: asignacion
                for asignacion in asignaciones
            }

            # Compatibilidad con doctores antiguos que todavía
            # tienen su especialidad únicamente en Doctor.
            if not por_id and doctor.especialidad_id_FK:
                especialidad_legacy = (
                    db.query(Especialidad)
                    .filter(
                        Especialidad.id_PK == doctor.especialidad_id_FK
                    )
                    .first()
                )

                if especialidad_legacy:
                    nueva_asignacion = DoctorEspecialidad(
                        doctor_id_FK=doctor.id_PK,
                        especialidad_id_FK=doctor.especialidad_id_FK
                    )

                    db.add(nueva_asignacion)
                    db.flush()

                    por_id[doctor.especialidad_id_FK] = nueva_asignacion

            # Verificar que todas las especialidades enviadas
            # estén realmente asignadas al doctor.
            ids_asignados = set(por_id.keys())
            ids_recibidos = set(ids_detalle)

            if not ids_recibidos.issubset(ids_asignados):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Solo puedes editar especialidades "
                        "asignadas a tu perfil."
                    )
                )

            # Actualizar los datos de cada especialidad.
            for item in detalles:
                especialidad_id = item["id_PK"]
                asignacion = por_id[especialidad_id]

                asignacion.cedula_profesional = (
                    item.get("cedula_profesional") or ""
                ).strip() or None

        # -----------------------------------------
        # 5. GUARDAR CAMBIOS
        # -----------------------------------------
        db.commit()
        db.refresh(doctor)

        return {
            "mensaje": "Tu perfil profesional se actualizó correctamente",
            "doctor": serializar_doctor(db, doctor)
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as error:
        db.rollback()

        print(
            f"Error al actualizar el perfil del doctor: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="No fue posible actualizar tu perfil profesional"
        )

def _obtener_doctor_actual(db: Session, usuario: Usuario) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario.id_PK).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Tu usuario todavía no tiene un perfil de médico")
    return doctor


@router.post("/perfil/especialidades/{especialidad_id}/documento", status_code=200)
def subir_documento_especialidad(
    especialidad_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_medico(usuario_actual)
    doctor = _obtener_doctor_actual(db, usuario_actual)
    asignacion = db.query(DoctorEspecialidad).filter(
        DoctorEspecialidad.doctor_id_FK == doctor.id_PK,
        DoctorEspecialidad.especialidad_id_FK == especialidad_id,
    ).first()
    if not asignacion:
        raise HTTPException(status_code=404, detail="La especialidad no está asignada a tu perfil.")
    if archivo.content_type not in ("application/pdf", "application/octet-stream") or not (archivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="El archivo debe ser un PDF.")
    contenido = archivo.file.read(10 * 1024 * 1024 + 1)
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El PDF no puede superar 10 MB.")
    if not contenido.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="El archivo seleccionado no es un PDF válido.")

    carpeta = Path("storage/documentos_doctores") / str(doctor.id_PK)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{especialidad_id}_{uuid4().hex}.pdf"
    try:
        destino.write_bytes(contenido)
        anterior = asignacion.documento_validez
        asignacion.documento_validez = destino.as_posix()
        db.commit()
        if anterior:
            anterior_path = Path(anterior)
            if anterior_path.exists() and anterior_path.is_file():
                anterior_path.unlink()
    except Exception:
        db.rollback()
        if destino.exists():
            destino.unlink()
        raise HTTPException(status_code=500, detail="No fue posible guardar el documento.")
    return {"mensaje": "Documento cargado correctamente.", "documento_validez": asignacion.documento_validez}


@router.get("/perfil/especialidades/{especialidad_id}/documento")
def descargar_documento_especialidad(
    especialidad_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_medico(usuario_actual)
    doctor = _obtener_doctor_actual(db, usuario_actual)
    asignacion = db.query(DoctorEspecialidad).filter(
        DoctorEspecialidad.doctor_id_FK == doctor.id_PK,
        DoctorEspecialidad.especialidad_id_FK == especialidad_id,
    ).first()
    if not asignacion or not asignacion.documento_validez:
        raise HTTPException(status_code=404, detail="No hay documento de validez registrado.")
    ruta = Path(asignacion.documento_validez)
    if not ruta.exists() or not ruta.is_file():
        raise HTTPException(status_code=404, detail="El documento ya no está disponible.")
    return FileResponse(ruta, media_type="application/pdf", filename="documento_validez.pdf")


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
            rfc=datos.rfc,
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
        .join(Doctor.usuario)
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

        if "rfc" in cambios:
            doctor.rfc = cambios["rfc"]

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

@router.get("/mis-pacientes")
def obtener_mis_pacientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Devuelve los pacientes que tienen citas con el doctor logueado.
    Solo accesible para doctores (rol 2).
    """

    # Solo doctores
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los doctores pueden ver sus pacientes"
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

    from app.models.cita import Cita
    from app.models.paciente import Paciente

    es_gratuito = False
    if usuario_actual.clinica and usuario_actual.clinica.plan:
        es_gratuito = (usuario_actual.clinica.plan.nombre or "").lower().strip() == "gratuito"

    if es_gratuito:
        pacientes = (
            db.query(Paciente)
            .filter(Paciente.clinica_id_FK == usuario_actual.clinica_id_FK)
            .order_by(Paciente.apellido, Paciente.nombre)
            .all()
        )
        return [
            {
                "id_PK": p.id_PK,
                "nombre": p.nombre,
                "apellido": p.apellido,
                "correo_electronico": p.correo_electronico,
                "telefono": p.telefono,
                "fecha_nacimiento": str(p.fecha_nacimiento) if p.fecha_nacimiento else None,
                "genero": p.genero,
                "direccion": p.direccion,
                "estado": p.estado,
            }
            for p in pacientes
        ]

    pacientes_ids = (
        db.query(Cita.paciente_id_FK)
        .filter(Cita.doctor_id_FK == doctor.id_PK)
        .distinct()
        .all()
    )

    # Extraer los IDs de los tuplos
    ids = [p[0] for p in pacientes_ids if p[0] is not None]

    # También los pacientes que otro médico le transfirió (aunque aún no tengan citas)
    from app.models.transferencia_paciente import TransferenciaPaciente
    transferidos = (
        db.query(TransferenciaPaciente.paciente_id_FK)
        .filter(TransferenciaPaciente.doctor_destino_id_FK == doctor.id_PK)
        .distinct()
        .all()
    )
    ids = list({*ids, *[t[0] for t in transferidos if t[0] is not None]})

    if not ids:
        return []

    # 3. Buscar los pacientes
    pacientes = (
        db.query(Paciente)
        .filter(Paciente.id_PK.in_(ids))
        .order_by(Paciente.apellido, Paciente.nombre)
        .all()
    )

    # 4. Serializar manualmente para incluir campos útiles
    return [
        {
            "id_PK": p.id_PK,
            "nombre": p.nombre,
            "apellido": p.apellido,
            "correo_electronico": p.correo_electronico,
            "telefono": p.telefono,
            "fecha_nacimiento": str(p.fecha_nacimiento) if p.fecha_nacimiento else None,
            "genero": p.genero,
            "direccion": p.direccion,
            "estado": p.estado,
        }
        for p in pacientes
    ]

@router.get("/lista-para-transferir")
def listar_doctores_para_transferir(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(status_code=403, detail="Solo los doctores pueden ver esta lista")

    doctor_actual = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
    
    doctores = (
        db.query(Doctor)
        .join(Doctor.usuario)
        .options(joinedload(Doctor.usuario), joinedload(Doctor.especialidad))
        .filter(
            Doctor.estado == "activo",
            Usuario.clinica_id_FK == usuario_actual.clinica_id_FK,
        )
        .all()
    )

    resultado = []
    for doc in doctores:
        if doctor_actual and doc.id_PK == doctor_actual.id_PK:
            continue
            
        resultado.append({
            "id_PK": doc.id_PK,
            "nombre": doc.usuario.nombre if doc.usuario else "Sin nombre",
            "especialidades": [
                {"nombre": doc.especialidad.nombre}
            ] if doc.especialidad else []
        })
    
    return resultado
