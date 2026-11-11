from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload

from app.core.security import crear_access_token, verificar_password
from app.models.clinica import Clinica
from app.models.usuario import Usuario

MENSAJE_CUENTA_DESACTIVADA = "Tu cuenta está desactivada. Contacta al administrador."
MENSAJE_CLINICA_SUSPENDIDA = (
    "El acceso a esta clínica ha sido suspendido. Por favor, contacte a soporte o regularice su suscripción."
)


class CuentaDesactivada(Exception):
    pass


class ClinicaSuspendida(Exception):
    pass


def es_superadmin_plataforma(usuario: Usuario) -> bool:
    return bool(usuario.is_superadmin)


def autenticar_usuario(
    db: Session,
    correo_electronico: str,
    password: str,
):
    usuario = (
        db.query(Usuario)
        .options(
            joinedload(Usuario.clinica),
            joinedload(Usuario.rol),
        )
        .filter(Usuario.correo_electronico == correo_electronico)
        .first()
    )

    if not usuario:
        return None

    if usuario.estado != "activo":
        return None

    if not verificar_password(password, usuario.hash_contrasena):
        if usuario.estado == "activo":
            usuario.intentos_fallidos += 1
            db.commit()
        return None

    clinica = usuario.clinica or (
        db.query(Clinica).filter(Clinica.id_PK == usuario.clinica_id_FK).first()
        if usuario.clinica_id_FK
        else None
    )

    if clinica is not None and not clinica.activa:
        if not es_superadmin_plataforma(usuario):
            raise ClinicaSuspendida()

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
        clinica_id=usuario.clinica_id_FK,
    )

    return {
        "usuario": usuario,
        "access_token": token,
    }
