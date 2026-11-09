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
