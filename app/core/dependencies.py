from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.database.connection import get_db
from app.models.clinica import Clinica
from app.models.role import Role
from app.models.usuario import Usuario
from app.services.auth_service import MENSAJE_CLINICA_SUSPENDIDA, es_superadmin_plataforma

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        usuario_id = payload.get("sub")
        clinica_id = payload.get("clinica_id")

        if usuario_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    usuario = (
        db.query(Usuario)
        .options(
            joinedload(Usuario.clinica),
            joinedload(Usuario.rol),
        )
        .filter(Usuario.id_PK == int(usuario_id))
        .first()
    )

    if usuario is None:
        raise credentials_exception

    if usuario.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario está inactivo",
        )

    if clinica_id is not None:
        usuario.clinica_id_FK = int(clinica_id)

    clinica = (
        db.query(Clinica)
        .filter(Clinica.id_PK == usuario.clinica_id_FK)
        .first()
        if usuario.clinica_id_FK
        else None
    )

    if clinica is not None and not clinica.activa:
        if not es_superadmin_plataforma(usuario):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=MENSAJE_CLINICA_SUSPENDIDA,
            )

    return usuario


def require_roles(allowed_roles: list[str]) -> Callable:
    allowed_lower = {r.lower() for r in allowed_roles}

    def _checker(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        rol = db.get(Role, current.rol_id_FK) if current.rol_id_FK else None
        rol_nombre = (rol.nombre if rol else "").lower()

        if rol_nombre not in allowed_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )

        return current

    return _checker


def require_enterprise_plan(
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(current, "clinica_id_FK", None)
    if not clinica_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene una clínica asociada.",
        )
    from app.services.suscripcion_service import obtener_clinica_con_plan
    _, plan = obtener_clinica_con_plan(db, clinica_id)
    nombre_plan = (plan.nombre or "").lower()
    nombre_plan = (
        nombre_plan.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .strip()
    )
    if "empresarial" not in nombre_plan:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Esta funcionalidad requiere una suscripción con Plan Empresarial activo.",
        )
    return current


def verificar_modulo_salas(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_salas", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye acceso a salas.",
            )
    return usuario


def verificar_modulo_almacen(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_almacen", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye acceso al almacén.",
            )
    return usuario


def verificar_modulo_reportes(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_reportes", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye acceso a reportes.",
            )
    return usuario


def verificar_modulo_auditoria(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_auditoria", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye acceso a auditoría.",
            )
    return usuario


def verificar_modulo_contratos(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_contratos", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye acceso a contratos.",
            )
    return usuario


def verificar_gestion_personal(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id:
        from app.services.suscripcion_service import obtener_clinica_con_plan
        _, plan = obtener_clinica_con_plan(db, clinica_id)
        if (plan.nombre or "").strip().lower() == "gratuito" or not getattr(plan, "incluye_roles", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso restringido: El plan Gratuito no incluye administración de personal ni roles.",
            )
    return usuario


