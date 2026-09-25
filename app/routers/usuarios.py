from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario
from app.models.role import Role
from app.schemas.usuario import UsuarioCrear, UsuarioResponse
from app.core.security import generar_hash_password
from app.core.dependencies import get_current_user


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

    usuario_existente = (
        db.query(Usuario)
        .filter(
            Usuario.correo_electronico
            == datos.correo_electronico
        )
        .first()
    )

    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese correo electrónico"
        )

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

    nuevo_usuario = Usuario(
        nombre=datos.nombre,
        correo_electronico=datos.correo_electronico,
        hash_contrasena=generar_hash_password(datos.password),
        rol_id_FK=datos.rol_id_FK,
        estado="activo",
        intentos_fallidos=0
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario