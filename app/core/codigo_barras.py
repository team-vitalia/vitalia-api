"""Utilidades puras para códigos de barras (sin dependencias de base de datos).

* `normalizar_codigo`: limpia lo que envía un lector (espacios, Enter, caracteres de control).
* `variantes_codigo`: EAN-13, UPC-A (12) y GTIN-14 son el mismo producto con ceros a la
  izquierda distintos; devuelve las variantes para encontrarlo sin importar cómo lo lea el lector.
* `parsear_gs1`: los DataMatrix / GS1-128 de los medicamentos traen GTIN (01), caducidad (17)
  y lote (10) en un solo código; se extraen para precargar el formulario de entrada.
"""
import calendar
from datetime import date

GS = "\x1d"  # separador FNC1 de los campos de longitud variable

# AI de longitud fija (cantidad de caracteres del valor)
_AI_FIJOS = {"00": 18, "01": 14, "02": 14, "11": 6, "12": 6, "13": 6, "15": 6, "16": 6, "17": 6, "20": 2}
# AI de longitud variable (máximo de caracteres)
_AI_VARIABLES = {"10": 20, "21": 20}


def normalizar_codigo(codigo: str | None) -> str:
    """Quita espacios y caracteres de control (p. ej. el salto de línea que manda el lector)."""
    if not codigo:
        return ""
    return "".join(ch for ch in str(codigo) if ch.isprintable()).strip()


def variantes_codigo(codigo: str | None) -> list[str]:
    """Variantes equivalentes de un código numérico (con distintos ceros a la izquierda)."""
    limpio = normalizar_codigo(codigo)
    if not limpio:
        return []
    variantes = [limpio]
    if limpio.isdigit():
        sin_ceros = limpio.lstrip("0")
        if sin_ceros:
            for ancho in (len(sin_ceros), 12, 13, 14):
                if ancho >= len(sin_ceros):
                    v = sin_ceros.zfill(ancho)
                    if v not in variantes:
                        variantes.append(v)
    return variantes


def _fecha_gs1(valor: str) -> date | None:
    """AAMMDD → date. Día 00 significa 'último día del mes' (norma GS1)."""
    if len(valor) != 6 or not valor.isdigit():
        return None
    anio, mes, dia = 2000 + int(valor[:2]), int(valor[2:4]), int(valor[4:])
    if not 1 <= mes <= 12:
        return None
    if dia == 0:
        dia = calendar.monthrange(anio, mes)[1]
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def parsear_gs1(crudo: str | None) -> dict | None:
    """Extrae {gtin, lote, caducidad} de un código GS1 (con o sin paréntesis).

    Devuelve None si el texto no parece GS1 (no empieza con el AI 01 y un GTIN de 14 dígitos).
    Si el lote queda ambiguo (campo variable sin separador y demasiado largo) se omite
    en lugar de adivinarlo.
    """
    if not crudo:
        return None
    texto = str(crudo).strip()
    if texto.startswith("("):
        # (01)0750...(17)271231(10)ABC → se quitan los paréntesis y se usa GS como separador
        texto = texto.replace("(", GS).replace(")", "").lstrip(GS)
    if not (texto.startswith("01") and len(texto) >= 16 and texto[2:16].isdigit()):
        return None

    resultado: dict = {"gtin": None, "lote": None, "caducidad": None}
    i, n = 0, len(texto)
    while i < n:
        if texto[i] == GS:
            i += 1
            continue
        ai = texto[i:i + 2]
        if ai in _AI_FIJOS:
            largo = _AI_FIJOS[ai]
            valor = texto[i + 2:i + 2 + largo]
            if len(valor) < largo:
                break
            if ai == "01":
                resultado["gtin"] = valor
            elif ai == "17":
                resultado["caducidad"] = _fecha_gs1(valor)
            i += 2 + largo
        elif ai in _AI_VARIABLES:
            fin = texto.find(GS, i + 2)
            valor = texto[i + 2:] if fin == -1 else texto[i + 2:fin]
            if valor and len(valor) <= _AI_VARIABLES[ai]:
                if ai == "10":
                    resultado["lote"] = valor.strip()
            i = n if fin == -1 else fin
        else:
            break  # AI desconocido: no se adivina el resto
    return resultado if resultado["gtin"] else None