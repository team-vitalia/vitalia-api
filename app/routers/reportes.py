from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import require_enterprise_plan, require_roles, verificar_modulo_reportes
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.services import ai_reports_service, reporte_export
from app.services.reporte_service import ReporteService

router = APIRouter(
    prefix="/api/reportes",
    tags=["Reportes"],
    dependencies=[Depends(verificar_modulo_reportes)],
)

ROLES_REPORTES = ["Administrador", "Coordinador"]

MIME = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class ConsultorIARequest(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=500)
    tipo: Optional[str] = "general"
    desde: Optional[date] = None
    hasta: Optional[date] = None


def _nombre_clinica(current: Usuario) -> str:
    clinica = getattr(current, "clinica", None)
    if clinica and getattr(clinica, "nombre_comercial", None):
        return str(clinica.nombre_comercial)
    return "Clínica VITALIA"


# ============================================================
# REPORTES OPERATIVOS (PLAN PROFESIONAL Y SUPERIOR)
# ============================================================

@router.get("/ocupacion-salas")
def ocupacion_salas(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None)).ocupacion_salas(desde, hasta)


@router.get("/citas-por-doctor")
def citas_por_doctor(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None)).citas_por_doctor(desde, hasta)


@router.get("/tiempos-espera")
def tiempos_espera(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None)).tiempos_espera(desde, hasta)


@router.get("/inventario-bajo")
def inventario_bajo(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    umbral: int = Query(10, ge=0),
):
    return ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None)).inventario_bajo(umbral)


@router.get("/recetas")
def recetas(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    return ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None)).recetas(desde, hasta)


@router.get("/{tipo}/exportar")
def exportar_reporte(
    tipo: str,
    formato: str = Query("pdf", pattern="^(pdf|excel)$"),
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_REPORTES)),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    umbral: int = Query(10, ge=0),
):
    """Descarga un reporte profesional en PDF o Excel con encabezado corporativo y gráfico corregido."""
    servicio = ReporteService(db, clinica_id=getattr(current, "clinica_id_FK", None))
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
    clinica_nombre = _nombre_clinica(current)
    if formato == "pdf":
        contenido, ext = reporte_export.a_pdf(rep, clinica_nombre=clinica_nombre), "pdf"
    else:
        contenido, ext = reporte_export.a_excel(rep, clinica_nombre=clinica_nombre), "xlsx"
    return Response(
        content=contenido,
        media_type=MIME[formato],
        headers={"Content-Disposition": f'attachment; filename="reporte_{tipo}.{ext}"'},
    )


# ============================================================
# REPORTES AVANZADOS E IA (EXCLUSIVO PLAN EMPRESARIAL)
# ============================================================

@router.get("/empresarial/datos")
async def obtener_datos_empresarial(
    tipo: str = Query("general"),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    umbral: int = Query(10, ge=0),
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_enterprise_plan),
):
    """Obtiene datos ejecutivos, comparativas históricas y diagnóstico estructurado por IA Groq."""
    clinica_id = getattr(current, "clinica_id_FK", None)
    servicio = ReporteService(db, clinica_id=clinica_id)
    clinica_nombre = _nombre_clinica(current)

    # 1. Datos del periodo actual
    resumen_actual = servicio.resumen_general(desde, hasta, umbral)

    # 2. Datos del periodo anterior equivalente
    ant_desde, ant_hasta = servicio.calcular_periodo_anterior(desde, hasta)
    resumen_anterior = servicio.resumen_general(ant_desde, ant_hasta, umbral)

    # 3. Comparativa porcentual
    comparativa = servicio.obtener_comparativa_metricas(resumen_actual, resumen_anterior)

    # 4. Contexto para IA Groq
    if tipo == "ocupacion":
        datos_especificos = servicio.ocupacion_salas(desde, hasta)
    elif tipo == "citas":
        datos_especificos = servicio.citas_por_doctor(desde, hasta)
    elif tipo == "espera":
        datos_especificos = servicio.tiempos_espera(desde, hasta)
    elif tipo == "inventario":
        datos_especificos = servicio.inventario_bajo(umbral)
    elif tipo == "recetas":
        datos_especificos = servicio.recetas(desde, hasta)
    else:
        datos_especificos = resumen_actual

    contexto_ia = {
        "tipo_reporte": tipo,
        "resumen_actual": {
            "total_citas": resumen_actual["total_citas"],
            "citas_atendidas": resumen_actual["citas_atendidas"],
            "citas_canceladas": resumen_actual["citas_canceladas"],
            "horas_ocupadas_totales": resumen_actual["horas_ocupadas_totales"],
            "espera_promedio_minutos": resumen_actual["espera_promedio_minutos"],
            "total_medicamentos_stock_bajo": resumen_actual["total_medicamentos_stock_bajo"],
            "total_recetas": resumen_actual["total_recetas"],
        },
        "comparativa": comparativa,
    }

    # 5. Generación de Insights con Groq (con fallback automático)
    insights_ia = await ai_reports_service.analizar_reporte_con_ia(
        datos_agregados=contexto_ia,
        clinica_nombre=clinica_nombre,
        tipo_reporte=tipo,
    )

    return {
        "tipo": tipo,
        "desde": resumen_actual["desde"],
        "hasta": resumen_actual["hasta"],
        "anterior_desde": resumen_anterior["desde"],
        "anterior_hasta": resumen_anterior["hasta"],
        "resumen_general": resumen_actual,
        "datos_especificos": datos_especificos,
        "comparativa": comparativa,
        "insights_ia": insights_ia,
    }


@router.post("/empresarial/consultor-ia")
async def consultar_ia_sobre_reporte(
    payload: ConsultorIARequest,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_enterprise_plan),
):
    """Consultor en tiempo real con Groq sobre las métricas y anomalías del reporte."""
    clinica_id = getattr(current, "clinica_id_FK", None)
    servicio = ReporteService(db, clinica_id=clinica_id)
    clinica_nombre = _nombre_clinica(current)

    resumen = servicio.resumen_general(payload.desde, payload.hasta)
    ant_desde, ant_hasta = servicio.calcular_periodo_anterior(payload.desde, payload.hasta)
    resumen_ant = servicio.resumen_general(ant_desde, ant_hasta)
    comp = servicio.obtener_comparativa_metricas(resumen, resumen_ant)

    contexto_consultor = {
        "citas": {
            "totales": resumen["total_citas"],
            "atendidas": resumen["citas_atendidas"],
            "canceladas": resumen["citas_canceladas"],
        },
        "salas": {
            "total": resumen["total_salas"],
            "horas_ocupadas": resumen["horas_ocupadas_totales"],
        },
        "tiempos_espera": {
            "promedio_minutos": resumen["espera_promedio_minutos"],
            "atenciones": resumen["total_atenciones_espera"],
        },
        "inventario": {
            "items_en_riesgo": resumen["total_medicamentos_stock_bajo"],
        },
        "recetas": {
            "total": resumen["total_recetas"],
        },
        "comparativa_periodo_anterior": comp,
    }

    respuesta = await ai_reports_service.responder_consulta_ia(
        pregunta=payload.pregunta,
        contexto_numerico=contexto_consultor,
        clinica_nombre=clinica_nombre,
    )
    return {"respuesta": respuesta}


@router.get("/empresarial/{tipo}/exportar")
async def exportar_reporte_empresarial(
    tipo: str,
    formato: str = Query("pdf", pattern="^(pdf|excel)$"),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    umbral: int = Query(10, ge=0),
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_enterprise_plan),
):
    """Descarga de reporte premium Empresarial: PDF Ejecutivo con IA o Excel Multi-hoja."""
    clinica_id = getattr(current, "clinica_id_FK", None)
    servicio = ReporteService(db, clinica_id=clinica_id)
    clinica_nombre = _nombre_clinica(current)

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
    elif tipo == "general":
        data = servicio.citas_por_doctor(desde, hasta)
    else:
        raise HTTPException(status_code=404, detail="Tipo de reporte desconocido")

    rep = reporte_export.preparar(tipo if tipo != "general" else "citas", data)

    resumen_act = servicio.resumen_general(desde, hasta, umbral)
    ant_desde, ant_hasta = servicio.calcular_periodo_anterior(desde, hasta)
    resumen_ant = servicio.resumen_general(ant_desde, ant_hasta, umbral)
    comparativa = servicio.obtener_comparativa_metricas(resumen_act, resumen_ant)

    contexto_ia = {
        "tipo_reporte": tipo,
        "resumen_actual": resumen_act,
        "comparativa": comparativa,
    }
    insights_ia = await ai_reports_service.analizar_reporte_con_ia(
        datos_agregados=contexto_ia,
        clinica_nombre=clinica_nombre,
        tipo_reporte=tipo,
    )

    if formato == "pdf":
        contenido = reporte_export.a_pdf_empresarial(
            rep=rep,
            comparativa=comparativa,
            insights_ia=insights_ia,
            clinica_nombre=clinica_nombre,
        )
        ext = "pdf"
    else:
        contenido = reporte_export.a_excel_empresarial(
            rep=rep,
            comparativa=comparativa,
            insights_ia=insights_ia,
            clinica_nombre=clinica_nombre,
        )
        ext = "xlsx"

    return Response(
        content=contenido,
        media_type=MIME[formato],
        headers={"Content-Disposition": f'attachment; filename="reporte_empresarial_{tipo}.{ext}"'},
    )
