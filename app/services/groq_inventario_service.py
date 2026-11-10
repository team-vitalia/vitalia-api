"""Análisis de abastecimiento con IA (Groq) a partir de las predicciones ya calculadas.

PRIVACIDAD: solo se envían datos AGREGADOS de inventario (artículo, existencias,
consumo, pronóstico). Nunca datos de pacientes, médicos ni usuarios.
La IA no calcula cifras: redacta alertas y recomendaciones sobre los números recibidos.
Si no hay clave de Groq o falla, se devuelve un análisis por reglas (`origen = "reglas"`).
"""
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("vitalia.analitica_ia")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "Eres el analista de abastecimiento de una clínica (sistema VITALIA). Recibes un JSON con el "
    "pronóstico de demanda de medicamentos, insumos y equipo, calculado por un modelo estadístico, "
    "y un resumen del consumo y las caducidades.\n"
    "REGLAS ESTRICTAS:\n"
    "1. Usa SOLO las cifras del JSON. No inventes artículos, cantidades ni fechas.\n"
    "2. Prioriza: agotado > critico > bajo, y los artículos con excedente_por_vencer (riesgo de merma).\n"
    "3. Si la confianza es 'baja' o 'sin_datos', dilo; si error_backtest_pct es alto, advierte la incertidumbre.\n"
    "4. No des consejos médicos ni clínicos; solo de abastecimiento. Recomienda que una persona revise antes de comprar.\n"
    "5. Responde en español, claro y breve.\n"
    "FORMATO: responde EXCLUSIVAMENTE con JSON válido:\n"
    '{"resumen": "2-3 frases con lo más importante",'
    ' "alertas": [{"articulo": "nombre exacto", "nivel": "critico|bajo|merma|info", "detalle": "motivo con cifras"}],'
    ' "recomendaciones": ["acciones concretas, p. ej. pedir N unidades de X"],'
    ' "observaciones": "limitaciones o supuestos"}'
)


def _modelos() -> list[str]:
    candidatos = []
    if settings.GROQ_MODEL:
        candidatos.append(settings.GROQ_MODEL)
    for extra in ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"):
        if extra not in candidatos:
            candidatos.append(extra)
    return candidatos


async def analizar_con_groq(datos: dict) -> dict:
    """Llama a Groq. Lanza RuntimeError si no se puede obtener una respuesta válida."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY no configurada")

    ultimo_error = None
    for modelo in _modelos():
        cuerpo = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(datos, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=40.0) as cliente:
                res = await cliente.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"},
                    json=cuerpo,
                )
            if res.status_code != 200:
                ultimo_error = f"HTTP {res.status_code}"
                logger.warning("Groq %s falló: %s", modelo, res.text[:200])
                continue
            parsed = json.loads(res.json()["choices"][0]["message"]["content"])
            return {
                "resumen": str(parsed.get("resumen", "")),
                "alertas": [a for a in parsed.get("alertas", []) if isinstance(a, dict)],
                "recomendaciones": [str(r) for r in parsed.get("recomendaciones", [])],
                "observaciones": str(parsed.get("observaciones", "")),
                "origen": "ia",
                "modelo": modelo,
            }
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
            ultimo_error = str(e)
            logger.warning("Groq %s error: %s", modelo, e)
    raise RuntimeError(ultimo_error or "Sin respuesta de Groq")


def analisis_por_reglas(items: list[dict], horizonte_dias: int) -> dict:
    """Alternativa sin IA: mismas conclusiones, redactadas con reglas fijas."""
    criticos = [i for i in items if i["riesgo"] in ("agotado", "critico")]
    bajos = [i for i in items if i["riesgo"] == "bajo"]
    merma = [i for i in items if i["excedente_por_vencer"] > 0]
    alertas = []
    for i in criticos[:8]:
        cobertura = "agotado" if i["riesgo"] == "agotado" else f"cobertura de {i['cobertura_dias']} días"
        alertas.append({"articulo": i["nombre"], "nivel": "critico",
                        "detalle": f"{cobertura}; demanda esperada {i['pronostico_horizonte']} u. en {horizonte_dias} días y existencia {i['stock_vigente']} u."})
    for i in bajos[:5]:
        alertas.append({"articulo": i["nombre"], "nivel": "bajo",
                        "detalle": f"cobertura de {i['cobertura_dias']} días; existencia {i['stock_vigente']} u."})
    for i in merma[:5]:
        alertas.append({"articulo": i["nombre"], "nivel": "merma",
                        "detalle": f"{i['excedente_por_vencer']} u. vencerán antes de usarse según la demanda esperada"})
    recomendaciones = [
        f"Pedir {i['sugerido_pedir']} {i['unidad_medida'] or 'u.'} de {i['nombre']}"
        for i in (criticos + bajos) if i["sugerido_pedir"] > 0
    ][:10]
    resumen = (
        f"En los próximos {horizonte_dias} días hay {len(criticos)} artículo(s) en riesgo crítico o agotados, "
        f"{len(bajos)} con stock bajo y {len(merma)} con riesgo de caducar sin usarse."
    )
    return {"resumen": resumen, "alertas": alertas, "recomendaciones": recomendaciones,
            "observaciones": "Análisis automático por reglas (sin IA). Estimación estadística: revísala antes de comprar.",
            "origen": "reglas", "modelo": None}
