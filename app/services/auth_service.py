from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.core.security import (
    verificar_password,
    crear_access_token
)


def autenticar_usuario(
    db: Session,
    correo_electronico: str,
    password: str
):
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.correo_electronico == correo_electronico
        )
        .first()
    )

    # Usuario no encontrado
    if not usuario:
        return None

    # Usuario bloqueado/inactivo
    if usuario.estado != "activo":
        return None

    # Contraseña incorrecta
    if not verificar_password(
        password,
        usuario.hash_contrasena
    ):
        usuario.intentos_fallidos += 1
        db.commit()

        return None

    # Login correcto
    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = datetime.now()

    db.commit()
    db.refresh(usuario)

    token = crear_access_token(
        {
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK
        }
    )

    return {
        "usuario": usuario,
        "access_token": token
    }