import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles, verificar_modulo_auditoria
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.schemas.auditoria import AuditoriaOut
from app.schemas.common import PageMeta, PageResponse
from app.services.auditoria_explicador import catalogo, explicar_lote
from app.services.auditoria_service import AuditoriaService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(verificar_modulo_auditoria)],
)

ROLES_AUDITORIA = ["Administrador", "Coordinador"]


def _servicio(db: Session, usuario: Usuario) -> AuditoriaService:
    return AuditoriaService(db, clinica_id=getattr(usuario, "clinica_id_FK", None))


def _explicaciones(db: Session, registros: list) -> list[dict]:
    """Frases en lenguaje sencillo. Es un complemento: si algo falla, el listado sigue funcionando."""
    try:
        resultado = explicar_lote(db, registros)
        if len(resultado) == len(registros):
            return resultado
    except Exception:
        logger.warning("No se pudieron generar las explicaciones de auditoría", exc_info=True)
    return [{} for _ in registros]


def _armar(reg, explicacion: dict) -> AuditoriaOut:
    return AuditoriaOut.model_validate({**AuditoriaOut.model_validate(reg).model_dump(), **explicacion})


def _rango(desde: Optional[datetime], hasta: Optional[datetime]) -> None:
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=400, detail="La fecha «desde» no puede ser posterior a «hasta».")


@router.get("/catalogo")
def catalogo_filtros(_: Usuario = Depends(require_roles(ROLES_AUDITORIA))):
    """Opciones (con nombres claros) para los filtros de la pantalla."""
    return catalogo()


@router.get("/resumen")
def resumen_actividad(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_AUDITORIA)),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
):
    """Cuánta actividad hubo por área y por tipo de acción (por defecto, últimos 30 días)."""
    _rango(desde, hasta)
    return _servicio(db, current).resumen(desde, hasta)


@router.get("", response_model=PageResponse[AuditoriaOut])
def listar_auditoria(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_AUDITORIA)),
    usuario_id: Optional[int] = Query(None),
    nombre_tabla: Optional[str] = Query(None),
    accion: Optional[str] = Query(None, description="Código técnico (compatibilidad)"),
    area: Optional[str] = Query(None, description="salas | inventario | citas | clinico | ia"),
    tipo_accion: Optional[str] = Query(None, description="crear | modificar | estado | eliminar | consultar | sala | ia"),
    buscar: Optional[str] = Query(None, max_length=100),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    _rango(desde, hasta)
    servicio = _servicio(db, current)
    items, total = servicio.listar(
        page=page, page_size=page_size, usuario_id=usuario_id, nombre_tabla=nombre_tabla, accion=accion,
        area=area, tipo_accion=tipo_accion, buscar=buscar, desde=desde, hasta=hasta,
    )
    items = list(items)
    explicaciones = _explicaciones(db, items)
    pages = (total + page_size - 1) // page_size
    return PageResponse[AuditoriaOut](
        data=[_armar(r, e) for r, e in zip(items, explicaciones)],
        meta=PageMeta(total=total, page=page, page_size=page_size, pages=pages),
    )


@router.get("/{registro_id}", response_model=AuditoriaOut)
def obtener_auditoria(
    registro_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_AUDITORIA)),
):
    reg = _servicio(db, current).obtener(registro_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return _armar(reg, _explicaciones(db, [reg])[0])
