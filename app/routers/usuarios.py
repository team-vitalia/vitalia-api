from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario
from app.models.role import Role
from sqlalchemy import func
from app.models.doctor_especialidad import DoctorEspecialidad
from app.schemas.usuario import (
    UsuarioCrear,
    UsuarioResponse,
    UsuarioActualizar
)
from app.core.security import generar_hash_password
from app.core.dependencies import get_current_user
from app.models.paciente import Paciente
from app.models.doctor import Doctor
from app.models.especialidad import Especialidad


router = APIRouter(
    prefix="/api/usuarios",
    tags=["Usuarios"]
)


@router.get("/")
def obtener_usuarios(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    
    # Solo el administrador puede consultar los usuarios
    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede consultar los usuarios"
        )

    usuarios = (
        db.query(Usuario)
        .order_by(Usuario.id_PK)
        .all()
    )

    return [
        {
            "id_PK": usuario.id_PK,
            "nombre": usuario.nombre,
            "correo_electronico": usuario.correo_electronico,
            "rol_id_FK": usuario.rol_id_FK,
            "rol": usuario.rol.nombre if usuario.rol else None,
            "estado": usuario.estado,
            "creado_en": usuario.creado_en,
            "ultimo_acceso": usuario.ultimo_acceso
        }
        for usuario in usuarios
    ]


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
    # Solo el administrador puede crear usuarios
    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede crear usuarios"
        )

    # Verificar correo
    usuario_existente = (
        db.query(Usuario)
        .filter(
            Usuario.correo_electronico == datos.correo_electronico
        )
        .first()
    )

    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese correo electrónico"
        )

    # Verificar rol
    rol = (
        db.query(Role)
        .filter(
            Role.id_PK == datos.rol_id_FK,
            Role.esta_activo == True
        )
        .first()
    )

    if not rol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol seleccionado no existe o está inactivo"
        )

    try:
        # ==========================================
        # 1. CREAR USUARIO
        # ==========================================

        nuevo_usuario = Usuario(
            nombre=datos.nombre,
            correo_electronico=datos.correo_electronico,
            hash_contrasena=generar_hash_password(datos.password),
            rol_id_FK=datos.rol_id_FK,
            estado="activo",
            telefono=datos.telefono,
            intentos_fallidos=0
        )

        db.add(nuevo_usuario)

        # Generamos el ID del usuario antes de continuar
        db.flush()

        # ==========================================
        # 2. SI ES DOCTOR
        # ==========================================

        
        if datos.rol_id_FK == 2:

            # Combinar la especialidad antigua con la nueva lista.
            especialidad_ids = list(datos.especialidad_ids)

            if datos.especialidad_id_FK is not None:
                if datos.especialidad_id_FK not in especialidad_ids:
                    especialidad_ids.append(datos.especialidad_id_FK)

            # Evitar especialidades duplicadas.
            if len(especialidad_ids) != len(set(especialidad_ids)):
                raise HTTPException(
                    status_code=422,
                    detail="No puedes asignar una especialidad más de una vez"
                )

            # Validar que todas existan y estén activas.
            if especialidad_ids:
                especialidades = (
                    db.query(Especialidad)
                    .filter(
                        Especialidad.id_PK.in_(especialidad_ids),
                        Especialidad.esta_activo.is_(True)
                    )
                    .all()
                )

                if len(especialidades) != len(especialidad_ids):
                    raise HTTPException(
                        status_code=400,
                        detail="Una o más especialidades no existen o están inactivas"
                    )

            # Validar licencia duplicada.
            licencia = (
                datos.numero_licencia.strip()
                if datos.numero_licencia
                else None
            )

            if licencia:
                duplicado = (
                    db.query(Doctor)
                    .filter(
                        func.lower(Doctor.numero_licencia) == licencia.lower()
                    )
                    .first()
                )

                if duplicado:
                    raise HTTPException(
                        status_code=409,
                        detail="El número de licencia ya está registrado"
                    )

            # Crear perfil del médico.
            nuevo_doctor = Doctor(
                usuario_id_FK=nuevo_usuario.id_PK,
                especialidad_id_FK=datos.especialidad_id_FK,
                numero_licencia=licencia,
                estado="activo",
                costo_consulta=datos.costo_consulta
            )

            db.add(nuevo_doctor)
            db.flush()

            # Guardar cada especialidad en doctor_especialidades.
            for especialidad_id in especialidad_ids:
                db.add(
                    DoctorEspecialidad(
                        doctor_id_FK=nuevo_doctor.id_PK,
                        especialidad_id_FK=especialidad_id
                    )
                )

        # ==========================================
        # 3. SI ES PACIENTE
        # ==========================================

        elif datos.rol_id_FK == 3:

            if not datos.apellido:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El apellido es obligatorio para pacientes"
                )

            nuevo_paciente = Paciente(
                # Relación entre paciente y usuario
                usuario_id_FK=nuevo_usuario.id_PK,

                nombre=datos.nombre,
                apellido=datos.apellido,
                fecha_nacimiento=datos.fecha_nacimiento,
                genero=datos.genero,
                telefono=datos.telefono,
                direccion=datos.direccion,
                correo_electronico=datos.correo_electronico,
                estado="activo"
            )

            db.add(nuevo_paciente)

        # ==========================================
        # 4. ADMIN / RECEPCIÓN
        # ==========================================
        # No necesitan registro adicional.

        db.commit()
        db.refresh(nuevo_usuario)

        return nuevo_usuario

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible crear el usuario"
        )


@router.patch("/{usuario_id}")
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Permite al administrador editar datos básicos,
    cambiar el rol cuando sea seguro y activar o desactivar cuentas.
    """

    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede actualizar usuarios"
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id_PK == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )

    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se recibieron cambios"
        )

    # Validar nombre.
    if "nombre" in cambios:
        nombre = (cambios["nombre"] or "").strip()

        if not nombre:
            raise HTTPException(
                status_code=422,
                detail="El nombre es obligatorio"
            )

        cambios["nombre"] = nombre

    # Validar que el correo no pertenezca a otra cuenta.
    if (
        "correo_electronico" in cambios
        and cambios["correo_electronico"] is not None
    ):
        correo = str(
            cambios["correo_electronico"]
        ).strip().lower()

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

    # Validar el estado.
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

        # No dejar el sistema sin administradores activos.
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

    # Validar cambios de rol.
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

    # Aplicar los cambios.
    try:
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)

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
        "nombre": usuario.nombre,
        "correo_electronico": usuario.correo_electronico,
        "telefono": usuario.telefono,
        "rol_id_FK": usuario.rol_id_FK,
        "rol": usuario.rol.nombre if usuario.rol else None,
        "estado": usuario.estado,
        "creado_en": usuario.creado_en,
        "ultimo_acceso": usuario.ultimo_acceso
    }