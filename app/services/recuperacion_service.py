"""Recuperación de contraseña de VITALIA.

El secreto nunca se guarda en claro. En usuarios.token_restablecimiento se
almacena: <tipo>:<expira_epoch>:<intentos>:<hmac_hex>
"""
import hashlib
import hmac
import secrets
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generar_hash_password
from app.models.usuario import Usuario
from app.services.email_service import construir_plantilla_base

TIPO_CORREO = "correo"
TIPO_QR = "qr"
TTL_SEGUNDOS = {TIPO_CORREO: 10 * 60, TIPO_QR: 10 * 60}
MAX_INTENTOS = 5
ESPERA_REENVIO_SEGUNDOS = 60


def _firmar(usuario_id: int, tipo: str, valor: str) -> str:
    mensaje = f"{usuario_id}:{tipo}:{valor}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), mensaje, hashlib.sha256).hexdigest()


def _leer(usuario: Usuario) -> dict | None:
    crudo = usuario.token_restablecimiento
    if not crudo:
        return None
    try:
        tipo, exp, intentos, firma = crudo.split(":", 3)
        if tipo not in TTL_SEGUNDOS:
            return None
        return {"tipo": tipo, "exp": int(exp), "intentos": int(intentos), "firma": firma}
    except (ValueError, AttributeError):
        return None


def _guardar(db: Session, usuario: Usuario, tipo: str, exp: int, intentos: int, firma: str) -> None:
    usuario.token_restablecimiento = f"{tipo}:{exp}:{intentos}:{firma}"
    db.commit()
    db.refresh(usuario)


def limpiar(db: Session, usuario: Usuario) -> None:
    usuario.token_restablecimiento = None
    db.commit()


def generar_codigo_correo() -> str:
    """Se conserva por compatibilidad con código antiguo; el nuevo flujo no lo usa."""
    return f"{secrets.randbelow(1_000_000):06d}"


def generar_token_correo() -> str:
    return secrets.token_urlsafe(32)


def generar_token_qr() -> str:
    return secrets.token_urlsafe(32)


def puede_reenviar(usuario: Usuario, tipo: str) -> bool:
    datos = _leer(usuario)
    if not datos or datos["tipo"] != tipo:
        return True
    emitido_en = datos["exp"] - TTL_SEGUNDOS[tipo]
    return time.time() - emitido_en >= ESPERA_REENVIO_SEGUNDOS


def emitir(db: Session, usuario: Usuario, tipo: str, valor: str) -> int:
    if tipo not in TTL_SEGUNDOS:
        raise ValueError("Tipo de recuperación no válido")
    exp = int(time.time()) + TTL_SEGUNDOS[tipo]
    _guardar(db, usuario, tipo, exp, 0, _firmar(usuario.id_PK, tipo, valor))
    return exp


def validar(db: Session, usuario: Usuario, tipo: str, valor: str) -> bool:
    datos = _leer(usuario)
    if not datos or datos["tipo"] != tipo:
        return False
    if datos["exp"] < time.time() or datos["intentos"] >= MAX_INTENTOS:
        limpiar(db, usuario)
        return False
    firma_recibida = _firmar(usuario.id_PK, tipo, valor)
    if hmac.compare_digest(datos["firma"], firma_recibida):
        return True
    intentos = datos["intentos"] + 1
    if intentos >= MAX_INTENTOS:
        limpiar(db, usuario)
    else:
        _guardar(db, usuario, tipo, datos["exp"], intentos, datos["firma"])
    return False


def cambiar_password(db: Session, usuario: Usuario, nueva_password: str) -> None:
    usuario.hash_contrasena = generar_hash_password(nueva_password)
    usuario.intentos_fallidos = 0
    usuario.token_restablecimiento = None
    db.commit()


def html_enlace_recuperacion(nombre: str, enlace: str) -> str:
    # El enlace se genera internamente con una URL base configurada y parámetros codificados.
    enlace_html = (enlace.replace("&", "&amp;").replace('"', "&quot;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
    return construir_plantilla_base(
        titulo="Restablece tu contraseña",
        subtitulo_badge="Recuperación de contraseña",
        color_badge_bg="rgb(226, 244, 240)",
        color_badge_txt="rgb(36, 127, 118)",
        filas_detalle=[
            ("Usuario", nombre),
            ("Acceso", f'<a href="{enlace_html}" style="color:rgb(36,127,118);font-weight:700;">Cambiar mi contraseña</a>'),
            ("Vigencia", f"{TTL_SEGUNDOS[TIPO_CORREO] // 60} minutos"),
        ],
        mensaje_adicional=(
            "Recibimos una solicitud para cambiar tu contraseña. Usa el enlace para establecer una nueva. "
            "Si no solicitaste este cambio, ignora este mensaje."
        ),
    )
