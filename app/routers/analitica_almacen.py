
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import (
    ROL_ADMIN,
    ROL_ALMACEN,
    ROL_COORDINADOR,
    clinica_de,
    exigir_rol,
)
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.services.groq_inventario_service import (
    analisis_por_reglas,
    analizar_con_groq,
)
from app.services.prediccion_service import (
    calcular_predicciones,
    panel_analitico,
)
from app.utils.auditoria import (
    ip_desde_request,
    registrar_auditoria,
)


# Configuración del logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/almacen/analitica",
    tags=["Analítica de almacén e IA"],
)

ROLES = [ROL_ADMIN, ROL_ALMACEN, ROL_COORDINADOR]

NOTA_METODO = (
    "Pronóstico estadístico (suavizado exponencial con tendencia amortiguada) "
    "sobre el consumo real. No considera brotes, campañas ni cambios "
    "extraordinarios: revísalo antes de comprar."
)


class AnalisisIARequest(BaseModel):
    horizonte_dias: int = Field(default=30, ge=7, le=90)
    tipo: str | None = Field(
        default=None,
        description="medicamento | insumo | equipo",
    )


@router.get("/panel")
def panel(
    meses: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Datos para las gráficas: consumo mensual, más consumidos, stock por tipo y caducidades."""

    exigir_rol(usuario_actual, ROLES)

    return panel_analitico(
        db,
        clinica_de(usuario_actual),
        meses,
    )


@router.get("/prediccion")
def prediccion(
    horizonte_dias: int = Query(30, ge=7, le=90),
    ventana_dias: int = Query(
        91,
        ge=28,
        le=182,
        description="Historial usado para predecir",
    ),
    tipo: str | None = Query(
        None,
        description="medicamento | insumo | equipo",
    ),
    solo_riesgo: bool = Query(
        False,
        description="Solo artículos agotados, críticos, bajos o con riesgo de merma",
    ),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """¿Qué medicamentos e insumos se ocuparán más y cuáles hay que reponer?"""

    exigir_rol(usuario_actual, ROLES)

    items = calcular_predicciones(
        db,
        clinica_de(usuario_actual),
        horizonte_dias,
        ventana_dias,
        tipo,
    )

    if solo_riesgo:
        items = [
            i for i in items
            if i["riesgo"] in ("agotado", "critico", "bajo")
            or i["excedente_por_vencer"] > 0
        ]

    conteo = {
        "agotado": 0,
        "critico": 0,
        "bajo": 0,
        "ok": 0,
        "sin_movimiento": 0,
    }

    for i in items:
        conteo[i["riesgo"]] += 1

    mas_demandados = sorted(
        items,
        key=lambda r: r["pronostico_horizonte"],
        reverse=True,
    )[:10]

    return {
        "generado": date.today().isoformat(),
        "horizonte_dias": horizonte_dias,
        "ventana_dias": ventana_dias,
        "nota": NOTA_METODO,
        "resumen_riesgo": conteo,
        "mas_demandados": [
            {
                "medicamento_id": i["medicamento_id"],
                "nombre": i["nombre"],
                "tipo_articulo": i["tipo_articulo"],
                "pronostico_horizonte": i["pronostico_horizonte"],
                "unidad_medida": i["unidad_medida"],
            }
            for i in mas_demandados
        ],
        "items": items[:limite],
    }


@router.post("/analisis-ia")
async def analisis_ia(
    datos: AnalisisIARequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """
    Análisis redactado por IA (Groq) sobre las predicciones.
    Si Groq no está disponible, utiliza reglas automáticas.
    """

    exigir_rol(usuario_actual, ROLES)

    clinica = clinica_de(usuario_actual)

    items = calcular_predicciones(
        db,
        clinica,
        datos.horizonte_dias,
        91,
        datos.tipo,
    )

    relevantes = [
        i for i in items
        if i["riesgo"] != "sin_movimiento"
        or i["excedente_por_vencer"] > 0
    ][:30]

    panel_datos = panel_analitico(db, clinica, 6)

    # Solo datos agregados de inventario:
    # no se envían pacientes ni usuarios a Groq.
    payload = {
        "horizonte_dias": datos.horizonte_dias,
        "fecha": date.today().isoformat(),
        "articulos": [
            {
                k: i[k]
                for k in (
                    "nombre",
                    "tipo_articulo",
                    "unidad_medida",
                    "stock_vigente",
                    "stock_minimo",
                    "consumo_ultimos_30d",
                    "pronostico_horizonte",
                    "cobertura_dias",
                    "riesgo",
                    "sugerido_pedir",
                    "tendencia_pct",
                    "confianza",
                    "error_backtest_pct",
                    "excedente_por_vencer",
                )
            }
            for i in relevantes
        ],
        "consumo_mensual": panel_datos["consumo_mensual"],
        "caducidad_unidades": panel_datos["caducidad_unidades"],
    }

    aviso = None

    try:
        logger.info(
            "Iniciando análisis con Groq. Artículos: %s, horizonte: %s días",
            len(relevantes),
            datos.horizonte_dias,
        )

        analisis = await analizar_con_groq(payload)

        logger.info("Análisis con Groq completado correctamente.")

    except Exception:
        # Registra el tipo de excepción, mensaje y traceback completo.
        # No registra la API Key ni el contenido de las credenciales.
        logger.exception(
            "ERROR AL GENERAR ANÁLISIS CON GROQ. "
            "Se utilizará el análisis automático por reglas."
        )

        # Mantener el mecanismo de respaldo existente.
        analisis = analisis_por_reglas(
            items,
            datos.horizonte_dias,
        )

        aviso = (
            "No se pudo usar la IA; "
            "se muestra un análisis automático por reglas."
        )

    registrar_auditoria(
        db,
        usuario_actual,
        "CONSULTAR",
        "analitica_inventario",
        None,
        None,
        {
            "horizonte_dias": datos.horizonte_dias,
            "origen": analisis["origen"],
        },
        ip=ip_desde_request(request),
        descripcion="Análisis de abastecimiento",
    )

    db.commit()

    return {
        **analisis,
        "aviso": aviso,
        "articulos_analizados": len(relevantes),
        "nota": NOTA_METODO,
    }
