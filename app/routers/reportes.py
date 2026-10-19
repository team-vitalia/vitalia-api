from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import require_roles
from app.models.usuario import Usuario
from app.services.reporte_service import ReporteService
from app.services import reporte_export

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])

ROLES_REPORTES = ["Administrador", "Coordinador"]


@router.get("/ocupacion-salas")
def ocupacion_salas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db).ocupacion_salas(desde, hasta)


@router.get("/citas-por-doctor")
def citas_por_doctor(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db).citas_por_doctor(desde, hasta)


@router.get("/tiempos-espera")
def tiempos_espera(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db).tiempos_espera(desde, hasta)


@router.get("/inventario-bajo")
def inventario_bajo(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    umbral: int = Query(10, ge=0),
):
    return ReporteService(db).inventario_bajo(umbral)


@router.get("/recetas")
def recetas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db).recetas(desde, hasta)


MIME = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/{tipo}/exportar")
def exportar_reporte(
    tipo: str,
    formato: str = Query("pdf", pattern="^(pdf|excel)$"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    umbral: int = Query(10, ge=0),
):
    """Descarga un reporte en PDF o Excel, ambos con gráfico."""
    servicio = ReporteService(db)
    if tipo == "ocupacion":
        data = servicio.ocupacion_salas(desde, hasta)
    elif tipo == "citas":
        data = servicio.citas_por_doctor(desde, hasta)
    elif tipo == "espera":
        data = servicio.tiempos_espera(desde, hasta)
    elif tipo == "inventario":
        data = servicio.inventario_bajo(umbral)
    elif tipo == "recetas":
        data = servicio.recetas(desde, hasta)
    else:
        raise HTTPException(status_code=404, detail="Tipo de reporte desconocido")

    rep = reporte_export.preparar(tipo, data)
    if formato == "pdf":
        contenido, ext = reporte_export.a_pdf(rep), "pdf"
    else:
        contenido, ext = reporte_export.a_excel(rep), "xlsx"
    return Response(
        content=contenido,
        media_type=MIME[formato],
        headers={"Content-Disposition": f'attachment; filename="reporte_{tipo}.{ext}"'},
    )
