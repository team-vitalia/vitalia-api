"""Posología y presentaciones comerciales (cajas, frascos...).

Reglas (sin acceso a base de datos, fáciles de probar):

* tomas      = ceil(24 × días / cada_N_horas)
* unidades   = ceil(dosis_por_toma × tomas)            → lo que TOMA el paciente
* presentaciones = ceil(unidades / unidades_por_presentacion) → lo que se SURTE

Ejemplo: 1 tableta cada 8 horas por 5 días = 15 tabletas; con cajas de 20
tabletas se surte 1 caja.
"""
import math
from decimal import ROUND_CEILING, Decimal

_INVARIABLES = {"ml", "mg", "g", "l", "cc", "ui", "mcg", "kg"}
_FRACCIONES = {Decimal("0.25"): "1/4", Decimal("0.5"): "1/2", Decimal("0.75"): "3/4"}


def calcular_tomas(frecuencia_horas: int, duracion_dias: int) -> int:
    if frecuencia_horas <= 0 or duracion_dias <= 0:
        raise ValueError("La frecuencia y la duración deben ser mayores a 0")
    return math.ceil(Decimal(24 * duracion_dias) / Decimal(frecuencia_horas))


def calcular_unidades_requeridas(dosis_unidades, frecuencia_horas: int, duracion_dias: int) -> int:
    dosis = Decimal(str(dosis_unidades))
    if dosis <= 0:
        raise ValueError("La dosis por toma debe ser mayor a 0")
    tomas = calcular_tomas(frecuencia_horas, duracion_dias)
    return int((dosis * tomas).to_integral_value(rounding=ROUND_CEILING))


def presentaciones_necesarias(unidades: int, unidades_por_presentacion: int) -> int:
    if unidades <= 0:
        raise ValueError("Las unidades requeridas deben ser mayores a 0")
    if unidades_por_presentacion <= 0:
        raise ValueError("Las unidades por presentación deben ser mayores a 0")
    return -(-int(unidades) // int(unidades_por_presentacion))


# ------------------------------------------------------------------ textos
def plural(unidad: str | None, cantidad: int | float | Decimal = 2) -> str:
    """Pluraliza una unidad en singular (caja→cajas, blíster→blísteres, ml→ml)."""
    u = (unidad or "").strip()
    if not u or Decimal(str(cantidad)) <= 1 or u.lower() in _INVARIABLES:
        return u
    if u[-1].lower() in "aeiouáéíóú":
        return u + "s"
    if u[-1].lower() == "z":
        return u[:-1] + "ces"
    return u + "es"


def formatear_numero(valor) -> str:
    d = Decimal(str(valor))
    if d in _FRACCIONES:
        return _FRACCIONES[d]
    entero, resto = divmod(d, 1)
    if resto in _FRACCIONES:
        return f"{int(entero)} {_FRACCIONES[resto]}"
    return f"{d.normalize():f}"


def texto_unidades(cantidad: int | float | Decimal, unidad_contenido: str | None) -> str:
    """'15 tabletas', '1 tableta', '5 ml'. Sin unidad: '15 u.'."""
    if not (unidad_contenido or "").strip():
        return f"{formatear_numero(cantidad)} u."
    return f"{formatear_numero(cantidad)} {plural(unidad_contenido, cantidad)}"


def texto_presentacion(
    unidad_presentacion: str | None,
    unidades_por_presentacion: int | None,
    unidad_contenido: str | None,
) -> str | None:
    """'Caja con 20 tabletas'."""
    if not unidades_por_presentacion:
        return None
    contenido = texto_unidades(unidades_por_presentacion, unidad_contenido)
    base = (unidad_presentacion or "Presentación").strip()
    return f"{base[:1].upper()}{base[1:]} con {contenido}"


def texto_surtir(
    cantidad: int,
    unidad_presentacion: str | None,
    unidades_por_presentacion: int | None,
    unidad_contenido: str | None,
) -> str:
    """'1 caja de 20 tabletas', '2 cajas de 20 tabletas', '3 frascos'."""
    unidad = (unidad_presentacion or "").strip() or "presentación"
    base = f"{cantidad} {plural(unidad, cantidad)}"
    if unidades_por_presentacion and unidades_por_presentacion > 1:
        return f"{base} de {texto_unidades(unidades_por_presentacion, unidad_contenido)}"
    return base


def texto_posologia(
    dosis_unidades, frecuencia_horas: int, duracion_dias: int, unidad_contenido: str | None
) -> dict[str, str]:
    """Textos legibles para los campos clásicos dosis / frecuencia / duración."""
    return {
        "dosis": texto_unidades(dosis_unidades, unidad_contenido),
        "frecuencia": f"Cada {frecuencia_horas} horas" if frecuencia_horas != 1 else "Cada hora",
        "duracion": f"{duracion_dias} día{'s' if duracion_dias != 1 else ''}",
    }


def item_receta_a_dict(it) -> dict:
    """Renglón de receta listo para la API, con la presentación a surtir explícita.

    `it` es un `ItemReceta` (no se importa el modelo para mantener este módulo puro).
    Lo usan el router de recetas y el expediente, para que ambos muestren lo mismo.
    """
    med = it.medicamento
    fuera = it.medicamento_id_FK is None
    unidad_pres = it.unidad_presentacion or (med.unidad_medida if med else None)
    unidad_cont = it.unidad_contenido or (med.unidad_contenido if med else None)
    upp = it.unidades_por_presentacion

    if it.cantidad_presentaciones and upp:
        cantidad_texto = texto_surtir(it.cantidad_presentaciones, unidad_pres, upp, unidad_cont)
        presentacion = cantidad_texto
    else:
        presentacion = med.presentacion if med else None
        if fuera and it.unidades_requeridas:
            cantidad_texto = texto_unidades(it.unidades_requeridas, unidad_cont)
        elif fuera and it.cantidad_presentaciones:
            cantidad_texto = f"{it.cantidad_presentaciones} presentación(es)"
        elif it.cantidad:
            cantidad_texto = f"{it.cantidad} {plural(unidad_pres, it.cantidad)}" if unidad_pres else f"{it.cantidad} u."
        else:
            cantidad_texto = None

    indicacion = None
    if it.unidades_requeridas:
        partes = [x for x in (it.dosis, it.frecuencia, it.duracion) if x]
        indicacion = f"{texto_unidades(it.unidades_requeridas, unidad_cont)} en total"
        if partes:
            indicacion += f" ({', '.join(partes)})"

    return {
        "id_PK": it.id_PK,
        "medicamento_id_FK": it.medicamento_id_FK,
        "medicamento": med.nombre if med else it.nombre_libre,
        "presentacion": presentacion,
        "dosis": it.dosis,
        "frecuencia": it.frecuencia,
        "duracion": it.duracion,
        "cantidad": it.cantidad,
        "cantidad_dispensada": it.cantidad_dispensada or 0,
        "instrucciones": it.instrucciones,
        "via_administracion": it.via_administracion,
        "cantidad_texto": cantidad_texto,
        "indicacion_texto": indicacion,
        "dosis_unidades": float(it.dosis_unidades) if it.dosis_unidades is not None else None,
        "frecuencia_horas": it.frecuencia_horas,
        "duracion_dias": it.duracion_dias,
        "unidades_requeridas": it.unidades_requeridas,
        "cantidad_presentaciones": it.cantidad_presentaciones,
        "unidades_por_presentacion": upp,
        "unidad_presentacion": unidad_pres,
        "unidad_contenido": unidad_cont,
        "fuera_de_catalogo": fuera,
        "no_disponible_farmacia": bool(it.no_disponible_farmacia),
    }