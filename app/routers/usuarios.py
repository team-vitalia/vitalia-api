from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_current_user
from app.core.security import generar_hash_password
from app.core.validaciones import (
    componer_apellido,
    normalizar_correo,
    validar_nombre_persona,
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
            "especialidades": perfil_doctor.get(usuario.id_PK, {}).get("especialidades", [])
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

    return usuario


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

    try:
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)

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
