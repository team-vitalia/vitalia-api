from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import get_current_user
from app.core.security import generar_hash_password
from app.core.validaciones import (
    componer_apellido,
    normalizar_correo,
    validar_nombre_persona,
    fecha_nacimiento_de_curp,
)
from app.database.connection import get_db
from app.models.doctor import Doctor
from app.models.doctor_especialidad import DoctorEspecialidad
from app.models.especialidad import Especialidad
from app.models.paciente import Paciente
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.usuario import (
    UsuarioActualizar,
    UsuarioCrear,
    UsuarioResponse,
)
from app.services.suscripcion_service import (
    validar_limite_personal,
    verificar_limite_pacientes,
    verificar_limite_personal,
)
from app.services.usuario_service import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_PACIENTE,
    crear_usuario_con_perfil,
)

router = APIRouter(
    prefix="/api/usuarios",
    tags=["Usuarios"]
)


def _perfil_paciente(db: Session, usuario_id: int) -> dict:
    ficha = (
        db.query(Paciente)
        .filter(Paciente.usuario_id_FK == usuario_id)
        .first()
    )
    if not ficha:
        return {
            "paciente_id": None,
            "curp": None,
            "fecha_nacimiento": None,
            "genero": None,
            "direccion": None,
        }
    return {
        "paciente_id": ficha.id_PK,
        "curp": ficha.curp,
        "fecha_nacimiento": ficha.fecha_nacimiento,
        "genero": ficha.genero,
        "direccion": ficha.direccion,
    }


@router.get("/")
def obtener_usuarios(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 5]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o coordinador pueden consultar los usuarios"
        )

    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    query_u = db.query(Usuario)
    if clinica_id is not None:
        query_u = query_u.filter(Usuario.clinica_id_FK == clinica_id)
    usuarios = query_u.order_by(Usuario.id_PK).all()

    nombres_especialidad = {
        e.id_PK: e.nombre for e in db.query(Especialidad).all()
    }

    asignadas: dict[int, list[dict]] = {}
    for fila in db.query(DoctorEspecialidad).all():
        asignadas.setdefault(fila.doctor_id_FK, []).append({
            "id_PK": fila.especialidad_id_FK,
            "nombre": nombres_especialidad.get(fila.especialidad_id_FK, "—")
        })

    perfil_doctor: dict[int, dict] = {}
    for doc in db.query(Doctor).all():
        lista = asignadas.get(doc.id_PK)

        if not lista and doc.especialidad_id_FK:
            lista = [{
                "id_PK": doc.especialidad_id_FK,
                "nombre": nombres_especialidad.get(doc.especialidad_id_FK, "—")
            }]

        perfil_doctor[doc.usuario_id_FK] = {
            "doctor_id": doc.id_PK,
            "numero_licencia": doc.numero_licencia,
            "rfc": doc.rfc,
            "costo_consulta": (
                float(doc.costo_consulta)
                if doc.costo_consulta is not None else None
            ),
            "especialidades": sorted(lista or [], key=lambda e: e["nombre"])
        }

    return [
        {
            "id_PK": usuario.id_PK,
            "clinica_id_FK": usuario.clinica_id_FK,
            "nombre": usuario.nombre,
            "apellido_paterno": usuario.apellido_paterno,
            "apellido_materno": usuario.apellido_materno,
            "correo_electronico": usuario.correo_electronico,
            "telefono": usuario.telefono,
            "rol_id_FK": usuario.rol_id_FK,
            "rol": usuario.rol.nombre if usuario.rol else None,
            "estado": usuario.estado,
            "creado_en": usuario.creado_en,
            "ultimo_acceso": usuario.ultimo_acceso,
            "doctor_id": perfil_doctor.get(usuario.id_PK, {}).get("doctor_id"),
            "numero_licencia": perfil_doctor.get(usuario.id_PK, {}).get("numero_licencia"),
            "rfc": perfil_doctor.get(usuario.id_PK, {}).get("rfc"),
            "costo_consulta": perfil_doctor.get(usuario.id_PK, {}).get("costo_consulta"),
            "especialidades": perfil_doctor.get(usuario.id_PK, {}).get("especialidades", []),
            **_perfil_paciente(db, usuario.id_PK),
        }
        for usuario in usuarios
    ]


@router.get("/{usuario_id}")
def obtener_usuario_por_id(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 5]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o coordinador pueden consultar los usuarios"
        )

    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    query_u = db.query(Usuario).filter(Usuario.id_PK == usuario_id)
    if clinica_id is not None:
        query_u = query_u.filter(Usuario.clinica_id_FK == clinica_id)
    usuario = query_u.first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )

    doctor = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == usuario.id_PK)
        .first()
    )
    especialidades = []
    if doctor:
        filas = (
            db.query(Especialidad)
            .join(DoctorEspecialidad, DoctorEspecialidad.especialidad_id_FK == Especialidad.id_PK)
            .filter(DoctorEspecialidad.doctor_id_FK == doctor.id_PK)
            .order_by(Especialidad.nombre)
            .all()
        )
        if not filas and doctor.especialidad:
            filas = [doctor.especialidad]
        especialidades = [{"id_PK": e.id_PK, "nombre": e.nombre} for e in filas]

    return {
        "id_PK": usuario.id_PK,
        "clinica_id_FK": usuario.clinica_id_FK,
        "nombre": usuario.nombre,
        "apellido_paterno": usuario.apellido_paterno,
        "apellido_materno": usuario.apellido_materno,
        "correo_electronico": usuario.correo_electronico,
        "telefono": usuario.telefono,
        "rol_id_FK": usuario.rol_id_FK,
        "rol": usuario.rol.nombre if usuario.rol else None,
        "estado": usuario.estado,
        "creado_en": usuario.creado_en,
        "ultimo_acceso": usuario.ultimo_acceso,
        "doctor_id": doctor.id_PK if doctor else None,
        "numero_licencia": doctor.numero_licencia if doctor else None,
        "rfc": doctor.rfc if doctor else None,
        "costo_consulta": float(doctor.costo_consulta) if doctor and doctor.costo_consulta is not None else None,
        "especialidades": especialidades,
        **_perfil_paciente(db, usuario.id_PK),
    }


@router.post(
    "/",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED
)
def crear_usuario(
    datos: UsuarioCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [ROL_ADMIN, ROL_COORDINADOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o coordinador pueden crear usuarios"
        )

    if (
        usuario_actual.rol_id_FK == ROL_COORDINADOR
        and datos.rol_id_FK in [ROL_ADMIN, ROL_COORDINADOR]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El coordinador no puede crear administradores ni coordinadores"
        )

    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El plan Gratuito no permite la administración de personal ni creación de nuevos usuarios.",
            )
        if datos.rol_id_FK == ROL_PACIENTE:
            verificar_limite_pacientes(db, clinica_id)
        else:
            verificar_limite_personal(db, clinica_id)

    return crear_usuario_con_perfil(
        db=db,
        datos=datos,
        hash_contrasena=generar_hash_password(datos.password),
        clinica_id=getattr(usuario_actual, "clinica_id_FK", None)
    )


@router.patch("/{usuario_id}")
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 5]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o coordinador pueden actualizar usuarios"
        )

    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    query_u = db.query(Usuario).filter(Usuario.id_PK == usuario_id)
    if clinica_id is not None:
        query_u = query_u.filter(Usuario.clinica_id_FK == clinica_id)
    usuario = query_u.first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )

    if (
        usuario_actual.rol_id_FK == 5
        and usuario.rol_id_FK in [1, 5]
        and usuario.id_PK != usuario_actual.id_PK
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El coordinador no puede modificar administradores ni coordinadores"
        )

    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se recibieron cambios"
        )

    if "nombre" in cambios:
        nombre = (cambios["nombre"] or "").strip()

        if not nombre:
            raise HTTPException(
                status_code=422,
                detail="El nombre es obligatorio"
            )

        try:
            cambios["nombre"] = validar_nombre_persona(nombre, "El nombre")
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

    for campo, etiqueta in (
        ("apellido_paterno", "El apellido paterno"),
        ("apellido_materno", "El apellido materno"),
    ):
        if campo in cambios:
            valor = (cambios[campo] or "").strip()

            if not valor:
                cambios[campo] = None
                continue

            try:
                cambios[campo] = validar_nombre_persona(valor, etiqueta)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error))

    if (
        usuario.rol_id_FK == ROL_PACIENTE
        and "apellido_paterno" in cambios
        and not cambios["apellido_paterno"]
    ):
        raise HTTPException(
            status_code=422,
            detail="El apellido paterno es obligatorio para pacientes"
        )

    if (
        "correo_electronico" in cambios
        and cambios["correo_electronico"] is not None
    ):
        correo = normalizar_correo(
            str(cambios["correo_electronico"])
        )

        duplicado = (
            db.query(Usuario)
            .filter(
                Usuario.correo_electronico == correo,
                Usuario.id_PK != usuario_id
            )
            .first()
        )

        if duplicado:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un usuario con ese correo electrónico"
            )

        cambios["correo_electronico"] = correo

    if "estado" in cambios:
        estado = (cambios["estado"] or "").strip().lower()

        if estado not in {"activo", "inactivo"}:
            raise HTTPException(
                status_code=422,
                detail="El estado debe ser activo o inactivo"
            )

        if (
            usuario.id_PK == usuario_actual.id_PK
            and estado == "inactivo"
        ):
            raise HTTPException(
                status_code=400,
                detail="No puedes desactivar tu propia cuenta"
            )

        if usuario.rol_id_FK == 1 and estado == "inactivo":
            administradores_activos = (
                db.query(Usuario)
                .filter(
                    Usuario.rol_id_FK == 1,
                    Usuario.estado == "activo"
                )
                .count()
            )

            if administradores_activos <= 1:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No puedes desactivar al último "
                        "administrador activo"
                    )
                )

        cambios["estado"] = estado

    if "rol_id_FK" in cambios:
        nuevo_rol_id = cambios["rol_id_FK"]

        if nuevo_rol_id is None:
            raise HTTPException(
                status_code=422,
                detail="Debes seleccionar un rol"
            )

        rol = (
            db.query(Role)
            .filter(
                Role.id_PK == nuevo_rol_id,
                Role.esta_activo.is_(True)
            )
            .first()
        )

        if not rol:
            raise HTTPException(
                status_code=400,
                detail="El rol seleccionado no existe o está inactivo"
            )

        if (
            usuario_actual.rol_id_FK == 5
            and nuevo_rol_id in [1, 5]
            and nuevo_rol_id != usuario.rol_id_FK
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El coordinador no puede asignar el rol de administrador ni de coordinador"
            )

        if nuevo_rol_id != usuario.rol_id_FK:
            tiene_perfil_doctor = (
                db.query(Doctor)
                .filter(Doctor.usuario_id_FK == usuario_id)
                .first()
                is not None
            )

            tiene_perfil_paciente = (
                db.query(Paciente)
                .filter(Paciente.usuario_id_FK == usuario_id)
                .first()
                is not None
            )

            if tiene_perfil_doctor or tiene_perfil_paciente:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La cuenta tiene un perfil clínico asociado. "
                        "No se puede cambiar su rol desde esta operación."
                    )
                )

            if usuario.rol_id_FK == 1 and nuevo_rol_id != 1:
                administradores_activos = (
                    db.query(Usuario)
                    .filter(
                        Usuario.rol_id_FK == 1,
                        Usuario.estado == "activo"
                    )
                    .count()
                )

                if administradores_activos <= 1:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "No puedes cambiar el rol del último "
                            "administrador activo"
                        )
                    )

    ficha_paciente = None
    if usuario.rol_id_FK == ROL_PACIENTE:
        ficha_paciente = (
            db.query(Paciente)
            .filter(Paciente.usuario_id_FK == usuario.id_PK)
            .first()
        )
        if not ficha_paciente:
            raise HTTPException(
                status_code=409,
                detail="La cuenta de paciente no tiene una ficha clínica asociada"
            )

        curp_final = cambios.get("curp", ficha_paciente.curp)
        fecha_final = cambios.get("fecha_nacimiento", ficha_paciente.fecha_nacimiento)

        if "curp" in cambios and not cambios["curp"]:
            raise HTTPException(status_code=422, detail="La CURP es obligatoria para pacientes")
        if "fecha_nacimiento" in cambios and not cambios["fecha_nacimiento"]:
            raise HTTPException(status_code=422, detail="La fecha de nacimiento es obligatoria para pacientes")
        if "genero" in cambios and not cambios["genero"]:
            raise HTTPException(status_code=422, detail="El género es obligatorio para pacientes")

        if curp_final and fecha_final and fecha_nacimiento_de_curp(curp_final) != fecha_final:
            raise HTTPException(
                status_code=422,
                detail="La fecha de nacimiento no coincide con la de la CURP"
            )

        if "curp" in cambios and cambios["curp"]:
            duplicada = (
                db.query(Paciente)
                .filter(
                    Paciente.curp == cambios["curp"],
                    Paciente.id_PK != ficha_paciente.id_PK
                )
                .first()
            )
            if duplicada:
                raise HTTPException(status_code=409, detail="La CURP ya está registrada")

    try:
        for campo, valor in cambios.items():
            if campo not in {"curp", "fecha_nacimiento", "genero", "direccion"}:
                setattr(usuario, campo, valor)

        if ficha_paciente:
            ficha_paciente.nombre = usuario.nombre
            ficha_paciente.apellido_paterno = usuario.apellido_paterno
            ficha_paciente.apellido_materno = usuario.apellido_materno
            ficha_paciente.apellido = componer_apellido(
                usuario.apellido_paterno,
                usuario.apellido_materno
            )
            ficha_paciente.correo_electronico = usuario.correo_electronico
            ficha_paciente.telefono = usuario.telefono
            for campo in ("curp", "fecha_nacimiento", "genero", "direccion"):
                if campo in cambios:
                    setattr(ficha_paciente, campo, cambios[campo])

        if (
            usuario.rol_id_FK == ROL_PACIENTE
            and ("apellido_paterno" in cambios or "apellido_materno" in cambios)
        ):
            ficha = (
                db.query(Paciente)
                .filter(Paciente.usuario_id_FK == usuario.id_PK)
                .first()
            )

            if ficha:
                ficha.apellido_paterno = usuario.apellido_paterno
                ficha.apellido_materno = usuario.apellido_materno
                ficha.apellido = componer_apellido(
                    usuario.apellido_paterno,
                    usuario.apellido_materno
                )

        db.commit()
        db.refresh(usuario)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible actualizar el usuario"
        )

    return {
        "id_PK": usuario.id_PK,
        "clinica_id_FK": usuario.clinica_id_FK,
        "nombre": usuario.nombre,
        "apellido_paterno": usuario.apellido_paterno,
        "apellido_materno": usuario.apellido_materno,
        "correo_electronico": usuario.correo_electronico,
        "telefono": usuario.telefono,
        "rol_id_FK": usuario.rol_id_FK,
        "rol": usuario.rol.nombre if usuario.rol else None,
        "estado": usuario.estado,
        "creado_en": usuario.creado_en,
        "ultimo_acceso": usuario.ultimo_acceso
    }

@router.delete("/{usuario_id}", status_code=status.HTTP_200_OK)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Elimina cuentas administrativas/no clínicas; protege doctores y pacientes."""
    if usuario_actual.rol_id_FK not in [ROL_ADMIN, ROL_COORDINADOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o coordinador pueden eliminar usuarios"
        )

    query = db.query(Usuario).filter(Usuario.id_PK == usuario_id)
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None:
        query = query.filter(Usuario.clinica_id_FK == clinica_id)
    objetivo = query.first()

    if not objetivo:
        raise HTTPException(status_code=404, detail="El usuario no existe")

    if objetivo.id_PK == usuario_actual.id_PK:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    if objetivo.rol_id_FK in [2, 3]:
        raise HTTPException(
            status_code=409,
            detail="No se pueden eliminar usuarios con rol de doctor o paciente"
        )

    tiene_perfil_doctor = (
        db.query(Doctor.id_PK)
        .filter(Doctor.usuario_id_FK == objetivo.id_PK)
        .first()
        is not None
    )
    tiene_perfil_paciente = (
        db.query(Paciente.id_PK)
        .filter(Paciente.usuario_id_FK == objetivo.id_PK)
        .first()
        is not None
    )
    if tiene_perfil_doctor or tiene_perfil_paciente:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar una cuenta que conserva un perfil clínico de doctor o paciente"
        )

    if (
        usuario_actual.rol_id_FK == ROL_COORDINADOR
        and objetivo.rol_id_FK in [ROL_ADMIN, ROL_COORDINADOR]
    ):
        raise HTTPException(
            status_code=403,
            detail="El coordinador no puede eliminar administradores ni coordinadores"
        )

    if objetivo.rol_id_FK == ROL_ADMIN:
        admins = db.query(Usuario).filter(Usuario.rol_id_FK == ROL_ADMIN)
        if clinica_id is not None:
            admins = admins.filter(Usuario.clinica_id_FK == clinica_id)
        if admins.count() <= 1:
            raise HTTPException(
                status_code=409,
                detail="No puedes eliminar al último administrador de la clínica"
            )

    try:
        db.delete(objetivo)
        db.commit()
        return {"mensaje": "Usuario eliminado correctamente", "id_PK": usuario_id}
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar este usuario porque tiene registros relacionados"
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible eliminar el usuario"
        )
