from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.registro_auditoria import RegistroAuditoria
from app.models.usuario import Usuario


def ip_desde_request(request) -> str | None:
    if not request:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def serializar(data: dict[str, Any]) -> dict[str, Any]:
    """Convierte date/datetime a string para guardar en JSON."""
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def registrar_auditoria(
    db: Session,
    usuario: Usuario | None,
    accion: str,
    tabla: str,
    id_registro: int,
    antiguos: dict | None,
    nuevos: dict | None,
    ip: str | None = None,
    descripcion: str | None = None,
) -> None:
    """Agrega un registro de auditoría a la sesión (el commit lo hace el llamador)."""
    db.add(
        RegistroAuditoria(
            usuario_id_FK=usuario.id_PK if usuario else None,
            accion=accion,
            nombre_tabla=tabla,
            id_registro=id_registro,
            valores_antiguos=antiguos,
            valores_nuevos=nuevos,
            descripcion=descripcion,
            direccion_ip=ip,
            marca_tiempo=datetime.now(),
        )
    )
