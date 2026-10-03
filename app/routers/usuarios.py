from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario
from app.models.role import Role
from app.schemas.usuario import UsuarioCrear, UsuarioResponse
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
                        detail="La especialidad seleccionada no existe"
                    )

            doctor_existente = (
                db.query(Doctor)
                .filter(
                    Doctor.usuario_id_FK == nuevo_usuario.id_PK
                )
                .first()
            )

            if doctor_existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este usuario ya está registrado como doctor"
                )

            nuevo_doctor = Doctor(
                usuario_id_FK=nuevo_usuario.id_PK,
                especialidad_id_FK=datos.especialidad_id_FK,
                numero_licencia=datos.numero_licencia,
                estado="activo",
                costo_consulta=datos.costo_consulta
            )

            db.add(nuevo_doctor)

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
