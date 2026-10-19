from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.auditoria import AuditoriaOut
from app.schemas.common import PageResponse, PageMeta
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/api/auditoria", tags=["Auditoría"])


@router.get("", response_model=PageResponse[AuditoriaOut])
def listar_auditoria(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
    usuario_id: Optional[int] = Query(None),
    nombre_tabla: Optional[str] = Query(None),
    accion: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = AuditoriaService(db).listar(
        usuario_id=usuario_id, nombre_tabla=nombre_tabla, accion=accion,
        desde=desde, hasta=hasta, page=page, page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return PageResponse[AuditoriaOut](
        data=[AuditoriaOut.model_validate(i) for i in items],
        meta=PageMeta(total=total, page=page, page_size=page_size, pages=pages),
    )


@router.get("/{registro_id}", response_model=AuditoriaOut)
def obtener_auditoria(
    registro_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    reg = AuditoriaService(db).obtener(registro_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return AuditoriaOut.model_validate(reg)
