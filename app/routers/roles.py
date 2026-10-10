
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.role import RoleActualizar, RoleCrear


router = APIRouter(
    prefix="/api/roles",
    tags=["Roles"]
)


def exigir_administrador(usuario_actual: Usuario) -> None:
    """
    Verifica que el usuario autenticado sea administrador.
    En VITALIA, el rol con ID 1 corresponde a Administrador.
    """
    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede gestionar los roles"
        )


@router.get("/")
def obtener_roles(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """
    Devuelve los roles activos.
    El administrador puede solicitar también los inactivos.
    """
    if incluir_inactivos:
        exigir_administrador(usuario_actual)

    consulta = db.query(Role)

    if not incluir_inactivos:
        consulta = consulta.filter(
            Role.esta_activo.is_(True)
        )

    roles = consulta.order_by(Role.id_PK).all()

    return [
        {
            "id_PK": rol.id_PK,
            "nombre": rol.nombre,
            "descripcion": rol.descripcion,
            "esta_activo": rol.esta_activo
        }
        for rol in roles
    ]


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED
)
def crear_rol(
    datos: RoleCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_administrador(usuario_actual)

    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre del rol es obligatorio"
        )

    existente = (
        db.query(Role)
        .filter(Role.nombre.ilike(nombre))
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un rol con ese nombre"
        )

    rol = Role(
        nombre=nombre,
        descripcion=datos.descripcion,
        esta_activo=True
    )

    db.add(rol)
    db.commit()
    db.refresh(rol)

    return {
        "id_PK": rol.id_PK,
        "nombre": rol.nombre,
        "descripcion": rol.descripcion,
        "esta_activo": rol.esta_activo
    }


@router.patch("/{rol_id}")
def actualizar_rol(
    rol_id: int,
    datos: RoleActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_administrador(usuario_actual)

    rol = (
        db.query(Role)
        .filter(Role.id_PK == rol_id)
        .first()
    )

    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El rol no existe"
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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El nombre del rol es obligatorio"
            )

        duplicado = (
            db.query(Role)
            .filter(
                Role.nombre.ilike(nombre),
                Role.id_PK != rol_id
            )
            .first()
        )

        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un rol con ese nombre"
            )

        cambios["nombre"] = nombre

    if cambios.get("esta_activo") is False:
        # No permitir desactivar el rol principal.
        if rol.id_PK == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede desactivar el rol Administrador"
            )

        usuarios_asignados = (
            db.query(Usuario)
            .filter(
                Usuario.rol_id_FK == rol_id,
                Usuario.estado == "activo"
            )
            .count()
        )

        if usuarios_asignados > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No se puede desactivar un rol que tiene "
                    "usuarios activos asignados"
                )
            )

    for campo, valor in cambios.items():
        setattr(rol, campo, valor)

    db.commit()
    db.refresh(rol)

    return {
        "id_PK": rol.id_PK,
        "nombre": rol.nombre,
        "descripcion": rol.descripcion,
        "esta_activo": rol.esta_activo
    }