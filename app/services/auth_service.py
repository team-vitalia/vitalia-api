from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.core.security import (
    verificar_password,
    crear_access_token
)


MENSAJE_CUENTA_DESACTIVADA = "Tu cuenta está desactivada. Contacta al administrador."


class CuentaDesactivada(Exception):
    """La persona se identificó correctamente, pero su cuenta no está activa."""


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

    if not usuario:
        return None

    if usuario.estado != "activo":
        return None

    if not verificar_password(
        password,
        usuario.hash_contrasena
    ):
        if usuario.estado == "activo":
            usuario.intentos_fallidos += 1
            db.commit()

        return None

    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = datetime.now()

    db.commit()
    db.refresh(usuario)

    token = crear_access_token(
        data={
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK,
            "clinica_id": usuario.clinica_id_FK,
        },
        clinica_id=usuario.clinica_id_FK
    )

    return {
        "usuario": usuario,
        "access_token": token
    }
