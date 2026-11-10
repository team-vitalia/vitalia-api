"""Predicción de demanda de medicamentos e insumos.

MÉTODO (estadístico, explicable, sin dependencias externas):
  1. Se toma el consumo real de los últimos `ventana_dias` (movimientos de tipo
     Dispensación, Consumo y Salida; las mermas NO cuentan como demanda).
  2. Se agrupa por semana y se ajusta un suavizado exponencial doble con tendencia
     amortiguada (Holt amortiguado) para proyectar las próximas semanas.
  3. Con pocos datos (< 3 semanas con consumo) se usa el promedio simple.
  4. Se mide la precisión con un backtest (error porcentual ponderado a 1 semana).

La IA (Groq) NO calcula nada: solo redacta recomendaciones a partir de estos números.
Es una estimación estadística: no considera brotes, campañas, cambios de proveedor
ni eventos extraordinarios, así que debe revisarla una persona antes de comprar.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.models.movimiento_inventario import MovimientoInventario
from app.models.tipo_movimiento_inventario import TipoMovimientoInventario
from app.services.inventario_service import (
    TIPO_CONSUMO, TIPO_DISPENSACION, TIPO_MERMA, TIPO_SALIDA, expresion_stock_vigente,
)

TIPOS_DEMANDA = (TIPO_DISPENSACION, TIPO_CONSUMO, TIPO_SALIDA)
ALPHA, BETA, PHI = 0.5, 0.3, 0.9


# ------------------------------------------------------------------ funciones puras
def a_fecha(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.fromisoformat(str(valor)[:19]).date()


def serie_semanal(consumo_diario: dict[date, float], hoy: date, semanas: int) -> list[float]:
    """Totales por semana; la última posición es la semana más reciente (termina hoy)."""
    serie = []
    for k in range(semanas):
        fin = hoy - timedelta(days=7 * (semanas - 1 - k))
        inicio = fin - timedelta(days=6)
        serie.append(sum(v for d, v in consumo_diario.items() if inicio <= d <= fin))
    return serie


def holt_amortiguado(serie: list[float], pasos: int) -> list[float]:
    """Pronóstico de los próximos `pasos` periodos (Holt con tendencia amortiguada)."""
    n = len(serie)
    if n == 0:
        return [0.0] * pasos
    nivel = serie[0]
    k = min(3, n - 1)
    tendencia = (serie[k] - serie[0]) / k if k > 0 else 0.0
    for y in serie[1:]:
        previo = nivel
        nivel = ALPHA * y + (1 - ALPHA) * (nivel + PHI * tendencia)
        tendencia = BETA * (nivel - previo) + (1 - BETA) * PHI * tendencia
    salida, acumulado = [], 0.0
    for h in range(1, pasos + 1):
        acumulado += PHI ** h
        salida.append(max(0.0, nivel + tendencia * acumulado))
    return salida


def pronostico_horizonte(serie: list[float], horizonte_dias: int) -> tuple[float, str]:
    """Unidades esperadas en `horizonte_dias`, y el método usado."""
    con_datos = sum(1 for x in serie if x > 0)
    if con_datos < 3:
        promedio_diario = sum(serie) / (len(serie) * 7) if serie else 0.0
        return promedio_diario * horizonte_dias, "promedio_simple"
    semanas_completas = horizonte_dias // 7
    resto = (horizonte_dias % 7) / 7
    pasos = semanas_completas + (1 if resto else 0)
    previsiones = holt_amortiguado(serie, pasos)
    total = sum(previsiones[:semanas_completas])
    if resto:
        total += previsiones[semanas_completas] * resto
    return total, "holt_amortiguado"


def error_backtest(serie: list[float], pruebas: int = 4) -> float | None:
    """WAPE (%) de pronósticos a 1 semana sobre las últimas semanas. None si hay pocos datos."""
    if len(serie) < pruebas + 4 or sum(serie) == 0:
        return None
    abs_err = real = 0.0
    for t in range(len(serie) - pruebas, len(serie)):
        pred = holt_amortiguado(serie[:t], 1)[0]
        abs_err += abs(pred - serie[t])
        real += serie[t]
    return round(100 * abs_err / real, 1) if real else None


def confianza(serie: list[float]) -> str:
    total = sum(serie)
    if total == 0:
        return "sin_datos"
    con_datos = sum(1 for x in serie if x > 0)
    media = total / len(serie)
    desv = math.sqrt(sum((x - media) ** 2 for x in serie) / len(serie))
    cv = desv / media if media else 9
    if con_datos >= 8 and cv < 0.6:
        return "alta"
    if con_datos >= 4 and cv < 1.0:
        return "media"
    return "baja"


def clasificar_riesgo(stock_efectivo: float, pronostico: float, horizonte: int, minimo: int, hay_consumo: bool) -> tuple[str, float | None]:
    """(riesgo, días de cobertura). riesgo: agotado | critico | bajo | ok | sin_movimiento."""
    if not hay_consumo or pronostico <= 0:
        return "sin_movimiento", None
    diario = pronostico / horizonte
    cobertura = stock_efectivo / diario if diario > 0 else None
    if stock_efectivo <= 0:
        return "agotado", 0.0
    if cobertura is not None and cobertura <= 7:
        return "critico", round(cobertura, 1)
    if (cobertura is not None and cobertura <= 15) or (minimo > 0 and stock_efectivo <= minimo):
        return "bajo", round(cobertura, 1) if cobertura is not None else None
    return "ok", round(cobertura, 1) if cobertura is not None else None


# ------------------------------------------------------------------ consultas
def _consumos_por_articulo(db: Session, clinica_id: int | None, desde: date) -> dict[int, dict[date, float]]:
    q = (
        db.query(Inventario.medicamento_id_FK, MovimientoInventario.creado_en, MovimientoInventario.cantidad)
        .join(MovimientoInventario, MovimientoInventario.inventario_id_FK == Inventario.id_PK)
        .join(TipoMovimientoInventario, MovimientoInventario.tipo_movimiento_FK == TipoMovimientoInventario.id_PK)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(
            TipoMovimientoInventario.nombre.in_(TIPOS_DEMANDA),
            MovimientoInventario.creado_en >= datetime.combine(desde, datetime.min.time()),
        )
    )
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    por_art: dict[int, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for med_id, creado, cantidad in q.all():
        por_art[med_id][a_fecha(creado)] += abs(cantidad or 0)
    return por_art


def calcular_predicciones(
    db: Session,
    clinica_id: int | None,
    horizonte_dias: int = 30,
    ventana_dias: int = 91,
    tipo: str | None = None,
    margen_seguridad: float = 0.2,
    hoy: date | None = None,
) -> list[dict]:
    """Pronóstico de demanda por artículo + stock, cobertura, riesgo y cantidad sugerida a pedir."""
    hoy = hoy or date.today()
    semanas = max(4, ventana_dias // 7)
    consumos = _consumos_por_articulo(db, clinica_id, hoy - timedelta(days=semanas * 7))

    articulos_q = db.query(Medicamento)
    if clinica_id is not None:
        articulos_q = articulos_q.filter(Medicamento.clinica_id_FK == clinica_id)
    if tipo:
        articulos_q = articulos_q.filter(Medicamento.tipo_articulo == tipo)
    articulos = articulos_q.all()
    ids = [a.id_PK for a in articulos]

    stock_por_art = {
        mid: int(s or 0)
        for mid, s in db.query(Inventario.medicamento_id_FK, expresion_stock_vigente())
        .filter(Inventario.medicamento_id_FK.in_(ids or [0]))
        .group_by(Inventario.medicamento_id_FK)
        .all()
    }
    limite = hoy + timedelta(days=horizonte_dias)
    por_vencer = {
        mid: int(s or 0)
        for mid, s in db.query(Inventario.medicamento_id_FK, func.sum(Inventario.stock_actual))
        .filter(
            Inventario.medicamento_id_FK.in_(ids or [0]),
            Inventario.stock_actual > 0,
            Inventario.fecha_vencimiento.isnot(None),
            Inventario.fecha_vencimiento >= hoy,
            Inventario.fecha_vencimiento <= limite,
        )
        .group_by(Inventario.medicamento_id_FK)
        .all()
    }

    resultado = []
    for art in articulos:
        diario = consumos.get(art.id_PK, {})
        serie = serie_semanal(diario, hoy, semanas)
        total = sum(serie)
        pronostico, metodo = pronostico_horizonte(serie, horizonte_dias)
        stock = stock_por_art.get(art.id_PK, 0)
        vence = por_vencer.get(art.id_PK, 0)
        # FEFO consume primero lo que vence antes: lo que exceda la demanda esperada se perderá
        excedente = max(0, vence - math.ceil(pronostico))
        stock_efectivo = max(0, stock - excedente)
        minimo = art.stock_minimo or 0
        riesgo, cobertura = clasificar_riesgo(stock_efectivo, pronostico, horizonte_dias, minimo, total > 0)
        objetivo = max(pronostico * (1 + margen_seguridad), float(minimo))
        sugerido = int(math.ceil(max(0.0, objetivo - stock_efectivo))) if (total > 0 or minimo > 0) else 0

        ultimas4 = sum(serie[-4:])
        previas = serie[:-4]
        base_prev = (sum(previas) / len(previas)) if previas else 0
        tendencia_pct = round(100 * ((ultimas4 / 4) - base_prev) / base_prev, 1) if base_prev > 0 else None

        resultado.append(
            {
                "medicamento_id": art.id_PK,
                "nombre": art.nombre,
                "presentacion": art.presentacion,
                "tipo_articulo": art.tipo_articulo or "medicamento",
                "unidad_medida": art.unidad_medida,
                "categoria": art.categoria,
                "stock_vigente": stock,
                "stock_minimo": minimo,
                "consumo_ventana": round(total),
                "consumo_ultimos_30d": round(sum(v for d, v in diario.items() if d > hoy - timedelta(days=30))),
                "consumo_diario_prom": round(total / (semanas * 7), 2),
                "tendencia_pct": tendencia_pct,
                "pronostico_horizonte": round(pronostico),
                "cobertura_dias": cobertura,
                "unidades_por_vencer": vence,
                "excedente_por_vencer": excedente,
                "sugerido_pedir": sugerido,
                "riesgo": riesgo,
                "metodo": metodo if total > 0 else "sin_datos",
                "confianza": confianza(serie),
                "error_backtest_pct": error_backtest(serie),
                "serie_semanal": [round(x) for x in serie],
            }
        )

    orden = {"agotado": 0, "critico": 1, "bajo": 2, "ok": 3, "sin_movimiento": 4}
    resultado.sort(key=lambda r: (orden[r["riesgo"]], r["cobertura_dias"] if r["cobertura_dias"] is not None else 9999, -r["pronostico_horizonte"]))
    return resultado


def panel_analitico(db: Session, clinica_id: int | None, meses: int = 6, hoy: date | None = None) -> dict:
    """Datos agregados para las gráficas del panel de almacén."""
    hoy = hoy or date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    meses_lista = []
    anio, mes = inicio_mes.year, inicio_mes.month
    for _ in range(meses):
        meses_lista.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    meses_lista.reverse()
    desde = date(meses_lista[0][0], meses_lista[0][1], 1)

    q = (
        db.query(
            Medicamento.id_PK, Medicamento.nombre, Medicamento.tipo_articulo,
            MovimientoInventario.creado_en, MovimientoInventario.cantidad, TipoMovimientoInventario.nombre,
        )
        .join(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .join(MovimientoInventario, MovimientoInventario.inventario_id_FK == Inventario.id_PK)
        .join(TipoMovimientoInventario, MovimientoInventario.tipo_movimiento_FK == TipoMovimientoInventario.id_PK)
        .filter(
            TipoMovimientoInventario.nombre.in_(TIPOS_DEMANDA + (TIPO_MERMA,)),
            MovimientoInventario.creado_en >= datetime.combine(desde, datetime.min.time()),
        )
    )
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)

    mensual = {m: {"medicamentos": 0, "insumos": 0, "merma": 0} for m in meses_lista}
    top: dict[int, dict] = {}
    corte_top = hoy - timedelta(days=90)
    for med_id, nombre, tipo_art, creado, cantidad, tipo_mov in q.all():
        fecha = a_fecha(creado)
        clave = (fecha.year, fecha.month)
        unidades = abs(cantidad or 0)
        if clave in mensual:
            if tipo_mov == TIPO_MERMA:
                mensual[clave]["merma"] += unidades
            elif (tipo_art or "medicamento") == "medicamento":
                mensual[clave]["medicamentos"] += unidades
            else:
                mensual[clave]["insumos"] += unidades
        if tipo_mov != TIPO_MERMA and fecha >= corte_top:
            fila = top.setdefault(med_id, {"medicamento_id": med_id, "nombre": nombre, "tipo_articulo": tipo_art or "medicamento", "unidades": 0})
            fila["unidades"] += unidades

    top_consumo = sorted(top.values(), key=lambda r: r["unidades"], reverse=True)[:10]

    lotes_q = db.query(Inventario, Medicamento).join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK).filter(Inventario.stock_actual > 0)
    if clinica_id is not None:
        lotes_q = lotes_q.filter(Medicamento.clinica_id_FK == clinica_id)
    stock_tipo: dict[str, dict] = defaultdict(lambda: {"unidades": 0, "valor": 0.0})
    caducidad = {"vencido": 0, "por_vencer_30": 0, "por_vencer_90": 0, "vigente": 0, "sin_fecha": 0}
    for lote, med in lotes_q.all():
        unidades = int(lote.stock_actual or 0)
        fv = lote.fecha_vencimiento
        if fv is None:
            caducidad["sin_fecha"] += unidades
        elif fv < hoy:
            caducidad["vencido"] += unidades
        else:
            if fv <= hoy + timedelta(days=30):
                caducidad["por_vencer_30"] += unidades
            elif fv <= hoy + timedelta(days=90):
                caducidad["por_vencer_90"] += unidades
            else:
                caducidad["vigente"] += unidades
            t = med.tipo_articulo or "medicamento"
            stock_tipo[t]["unidades"] += unidades
            stock_tipo[t]["valor"] += unidades * float(lote.precio_venta or 0)

    return {
        "consumo_mensual": [
            {"mes": f"{a}-{m:02d}", **mensual[(a, m)]} for (a, m) in meses_lista
        ],
        "top_consumo_90d": top_consumo,
        "stock_por_tipo": [
            {"tipo_articulo": t, "unidades": v["unidades"], "valor": round(v["valor"], 2)} for t, v in sorted(stock_tipo.items())
        ],
        "caducidad_unidades": caducidad,
    }
