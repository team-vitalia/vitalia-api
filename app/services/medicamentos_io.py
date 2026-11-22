"""Importación y exportación del catálogo de medicamentos (Excel y PDF).

* `a_excel`        → catálogo actual en .xlsx (mismas columnas que acepta la importación).
* `plantilla_excel`→ .xlsx vacío con ejemplos, validaciones e instrucciones.
* `a_pdf`          → lista imprimible del catálogo.
* `leer_filas_excel` / `normalizar_fila` → parseo y validación de cada fila importada.

Todo es puro (sin base de datos): el router decide qué hacer con las filas válidas.
"""
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.codigo_barras import normalizar_codigo

MAX_FILAS_IMPORTACION = 2000
MAX_BYTES_IMPORTACION = 5 * 1024 * 1024  # 5 MB

TIPOS_VALIDOS = ("medicamento", "insumo", "equipo")
_ALIAS_TIPO = {
    "medicamento": "medicamento", "medicamentos": "medicamento", "medicina": "medicamento",
    "insumo": "insumo", "insumos": "insumo",
    "equipo": "equipo", "equipos": "equipo", "equipo medico": "equipo",
}
_SI = {"si", "s", "yes", "y", "true", "verdadero", "1", "x"}
_NO = {"no", "n", "false", "falso", "0", ""}

# (clave interna, encabezado visible, ancho de columna)
COLUMNAS: list[tuple[str, str, int]] = [
    ("nombre", "Nombre*", 34),
    ("principio_activo", "Principio activo", 26),
    ("presentacion", "Presentación", 26),
    ("categoria", "Categoría", 20),
    ("tipo_articulo", "Tipo", 14),
    ("unidad_medida", "Unidad de medida", 16),
    ("requiere_receta", "Requiere receta", 16),
    ("stock_minimo", "Stock mínimo", 14),
    ("codigo_barras", "Código de barras", 20),
    ("descripcion", "Descripción", 40),
]
COLUMNA_STOCK_ACTUAL = ("stock_actual", "Stock actual (solo lectura)", 18)

VERDE = "0F4C45"
VERDE_CLARO = "E2F4F0"
GRIS_BORDE = "CBD5E1"


# ------------------------------------------------------------
# Utilidades de texto
# ------------------------------------------------------------
def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _clave_encabezado(texto: Any) -> str:
    """'Código de barras *' → 'codigo de barras' (sin acentos, asteriscos ni paréntesis)."""
    t = _sin_acentos(str(texto or "")).lower()
    if "(" in t:
        t = t.split("(")[0]
    return " ".join(t.replace("*", " ").split())


_ENCABEZADOS = {
    "nombre": "nombre",
    "principio activo": "principio_activo",
    "presentacion": "presentacion",
    "categoria": "categoria",
    "tipo": "tipo_articulo",
    "tipo de articulo": "tipo_articulo",
    "unidad de medida": "unidad_medida",
    "unidad": "unidad_medida",
    "requiere receta": "requiere_receta",
    "receta": "requiere_receta",
    "stock minimo": "stock_minimo",
    "codigo de barras": "codigo_barras",
    "codigo": "codigo_barras",
    "descripcion": "descripcion",
}


def _texto(valor: Any) -> str:
    """Celda → texto limpio. Los números enteros guardados como float (7501.0) pierden el '.0'."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def campos_presentes(datos: dict[str, Any]) -> set[str]:
    """Columnas que traen valor en la fila (en modo «actualizar» una celda vacía no borra el dato)."""
    return {k for k, v in datos.items() if _texto(v) != ""}


def clave_nombre(nombre: str | None, presentacion: str | None) -> str:
    """Clave para detectar duplicados cuando no hay código de barras."""
    n = " ".join(_sin_acentos(nombre or "").lower().split())
    p = " ".join(_sin_acentos(presentacion or "").lower().split())
    return f"{n}|{p}"


# ------------------------------------------------------------
# Lectura y validación de la importación
# ------------------------------------------------------------
class ArchivoInvalido(Exception):
    """El archivo no se puede procesar (formato, tamaño o encabezados)."""


def leer_filas_excel(contenido: bytes) -> list[tuple[int, dict[str, Any]]]:
    """Devuelve [(numero_fila_excel, {clave: valor_crudo})] ignorando filas vacías."""
    if not contenido:
        raise ArchivoInvalido("El archivo está vacío.")
    if len(contenido) > MAX_BYTES_IMPORTACION:
        raise ArchivoInvalido("El archivo supera el tamaño máximo permitido (5 MB).")
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise ArchivoInvalido("No se pudo leer el archivo. Usa un Excel .xlsx (puedes descargar la plantilla).")

    hoja = libro["Medicamentos"] if "Medicamentos" in libro.sheetnames else libro.worksheets[0]
    filas = hoja.iter_rows(values_only=True)
    try:
        encabezados = next(filas)
    except StopIteration:
        raise ArchivoInvalido("El archivo no tiene filas.")

    mapa: dict[int, str] = {}
    for idx, titulo in enumerate(encabezados):
        clave = _ENCABEZADOS.get(_clave_encabezado(titulo))
        if clave and clave not in mapa.values():
            mapa[idx] = clave
    if "nombre" not in mapa.values():
        raise ArchivoInvalido("No se encontró la columna «Nombre». Usa la plantilla de importación.")

    resultado: list[tuple[int, dict[str, Any]]] = []
    for numero, fila in enumerate(filas, start=2):
        datos = {clave: fila[idx] if idx < len(fila) else None for idx, clave in mapa.items()}
        if all(_texto(v) == "" for v in datos.values()):
            continue  # fila vacía
        resultado.append((numero, datos))
        if len(resultado) > MAX_FILAS_IMPORTACION:
            raise ArchivoInvalido(f"El archivo tiene más de {MAX_FILAS_IMPORTACION} filas; divídelo en varios.")
    if not resultado:
        raise ArchivoInvalido("El archivo no tiene medicamentos para importar.")
    return resultado


_LIMITES = {
    "nombre": 200, "principio_activo": 200, "presentacion": 100,
    "categoria": 100, "unidad_medida": 30, "codigo_barras": 100,
}


def normalizar_fila(datos: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Valida una fila. Devuelve (datos_limpios, None) o (None, mensaje_de_error)."""
    limpio: dict[str, Any] = {}

    for campo in ("nombre", "principio_activo", "presentacion", "categoria", "unidad_medida", "descripcion"):
        limpio[campo] = _texto(datos.get(campo)) or None
    limpio["codigo_barras"] = normalizar_codigo(_texto(datos.get("codigo_barras"))) or None

    if not limpio["nombre"]:
        return None, "El nombre es obligatorio."
    for campo, maximo in _LIMITES.items():
        valor = limpio.get(campo)
        if valor and len(valor) > maximo:
            return None, f"«{campo.replace('_', ' ')}» supera {maximo} caracteres."

    tipo_txt = _sin_acentos(_texto(datos.get("tipo_articulo"))).lower()
    if tipo_txt == "":
        limpio["tipo_articulo"] = "medicamento"
    elif tipo_txt in _ALIAS_TIPO:
        limpio["tipo_articulo"] = _ALIAS_TIPO[tipo_txt]
    else:
        return None, f"Tipo «{_texto(datos.get('tipo_articulo'))}» no válido (usa medicamento, insumo o equipo)."

    receta_txt = _sin_acentos(_texto(datos.get("requiere_receta"))).lower()
    if receta_txt in _SI:
        limpio["requiere_receta"] = True
    elif receta_txt in _NO:
        limpio["requiere_receta"] = False
    else:
        return None, f"«Requiere receta» debe ser Sí o No (recibido «{_texto(datos.get('requiere_receta'))}»)."
    if limpio["tipo_articulo"] != "medicamento":
        limpio["requiere_receta"] = False  # los insumos y el equipo no se recetan

    minimo_txt = _texto(datos.get("stock_minimo"))
    if minimo_txt == "":
        limpio["stock_minimo"] = 0
    else:
        try:
            minimo = float(minimo_txt.replace(",", "."))
        except ValueError:
            return None, f"«Stock mínimo» debe ser un número entero (recibido «{minimo_txt}»)."
        if minimo < 0 or not minimo.is_integer():
            return None, "«Stock mínimo» debe ser un entero mayor o igual a 0."
        limpio["stock_minimo"] = int(minimo)

    return limpio, None


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
_BORDE = Border(*(Side(style="thin", color=GRIS_BORDE),) * 4)


def _estilo_encabezado(hoja, columnas: list[tuple[str, str, int]]) -> None:
    for i, (_, titulo, ancho) in enumerate(columnas, start=1):
        celda = hoja.cell(row=1, column=i, value=titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=VERDE)
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        celda.border = _BORDE
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    hoja.row_dimensions[1].height = 30
    hoja.freeze_panes = "A2"


def _validaciones(hoja, filas: int = 2000) -> None:
    """Listas desplegables para Tipo y Requiere receta."""
    tipos = DataValidation(type="list", formula1='"medicamento,insumo,equipo"', allow_blank=True)
    receta = DataValidation(type="list", formula1='"Sí,No"', allow_blank=True)
    minimo = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    hoja.add_data_validation(tipos)
    hoja.add_data_validation(receta)
    hoja.add_data_validation(minimo)
    tipos.add(f"E2:E{filas}")
    receta.add(f"G2:G{filas}")
    minimo.add(f"H2:H{filas}")


def _formato_texto_codigo(hoja, filas: int) -> None:
    """El código de barras se guarda como texto para que Excel no lo convierta a notación científica."""
    for fila in range(2, max(filas, 2) + 1):
        hoja.cell(row=fila, column=9).number_format = "@"


def a_excel(medicamentos: list[dict]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Medicamentos"
    columnas = COLUMNAS + [COLUMNA_STOCK_ACTUAL]
    _estilo_encabezado(hoja, columnas)

    for fila, m in enumerate(medicamentos, start=2):
        valores = [
            m.get("nombre"), m.get("principio_activo"), m.get("presentacion"), m.get("categoria"),
            m.get("tipo_articulo") or "medicamento", m.get("unidad_medida"),
            "Sí" if m.get("requiere_receta") else "No", m.get("stock_minimo") or 0,
            m.get("codigo_barras"), m.get("descripcion"), m.get("stock_actual") or 0,
        ]
        for col, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=col, value=valor)
            celda.border = _BORDE
            celda.alignment = Alignment(vertical="top", wrap_text=(col == 10))
        if fila % 2 == 1:
            for col in range(1, len(columnas) + 1):
                hoja.cell(row=fila, column=col).fill = PatternFill("solid", fgColor="F8FAFC")
        hoja.cell(row=fila, column=9).number_format = "@"
        hoja.cell(row=fila, column=11).font = Font(color="64748B", italic=True)

    _validaciones(hoja, max(len(medicamentos) + 1, 2000))
    hoja.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}{max(len(medicamentos) + 1, 2)}"

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def plantilla_excel() -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Medicamentos"
    _estilo_encabezado(hoja, COLUMNAS)

    ejemplos = [
        ["Paracetamol", "Paracetamol", "500 mg, caja con 20 tabletas", "Analgésico", "medicamento",
         "caja", "No", 20, "7501234567890", "Analgésico y antipirético"],
        ["Amoxicilina", "Amoxicilina", "500 mg, caja con 12 cápsulas", "Antibiótico", "medicamento",
         "caja", "Sí", 15, "7509876543210", "Antibiótico de amplio espectro"],
    ]
    for fila, valores in enumerate(ejemplos, start=2):
        for col, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=col, value=valor)
            celda.border = _BORDE
            celda.font = Font(color="94A3B8", italic=True)
    _formato_texto_codigo(hoja, 2000)
    _validaciones(hoja)

    guia = libro.create_sheet("Instrucciones")
    guia.column_dimensions["A"].width = 24
    guia.column_dimensions["B"].width = 90
    filas = [
        ("Cómo importar", ""),
        ("1.", "Llena la hoja «Medicamentos» (una fila por medicamento). Borra las dos filas de ejemplo."),
        ("2.", "Guarda el archivo como .xlsx y súbelo desde Medicamentos → Importar Excel."),
        ("", ""),
        ("Columna", "Reglas"),
        ("Nombre*", "Obligatorio. Máximo 200 caracteres."),
        ("Principio activo", "Opcional. Máximo 200 caracteres."),
        ("Presentación", "Opcional. Ej. «500 mg, caja con 20 tabletas». Máximo 100 caracteres."),
        ("Categoría", "Opcional. Ej. Analgésico. Máximo 100 caracteres."),
        ("Tipo", "medicamento, insumo o equipo. Vacío = medicamento."),
        ("Unidad de medida", "Opcional. Ej. pieza, caja, frasco. Máximo 30 caracteres."),
        ("Requiere receta", "Sí o No. Vacío = No. Solo aplica a medicamentos."),
        ("Stock mínimo", "Entero ≥ 0 para la alerta de reposición (0 = usar el umbral general)."),
        ("Código de barras", "Opcional. Es lo que se escanea en la entrada de mercancía."),
        ("Descripción", "Opcional."),
        ("", ""),
        ("Duplicados", "Un medicamento ya existe si coincide el código de barras o, sin código, el nombre + presentación. "
                       "Al importar eliges si los existentes se omiten o se actualizan."),
        ("Existencias", "Este archivo solo da de alta el catálogo. Las existencias y lotes se registran en «Entrada por código de barras»."),
    ]
    for i, (a, b) in enumerate(filas, start=1):
        guia.cell(row=i, column=1, value=a).font = Font(bold=True)
        celda = guia.cell(row=i, column=2, value=b)
        celda.alignment = Alignment(wrap_text=True, vertical="top")
    guia["A1"].font = Font(bold=True, size=13, color=VERDE)
    for col in ("A5", "B5"):
        guia[col].font = Font(bold=True, color="FFFFFF")
        guia[col].fill = PatternFill("solid", fgColor=VERDE)

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ------------------------------------------------------------
# PDF
# ------------------------------------------------------------
def a_pdf(medicamentos: list[dict], clinica_nombre: str, filtro: str | None = None) -> bytes:
    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=landscape(A4),
        leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.4 * cm, bottomMargin=1.6 * cm,
        title="Lista de medicamentos", author="VITALIA",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=estilos["Title"], textColor=colors.HexColor(f"#{VERDE}"),
                            fontSize=18, alignment=0, spaceAfter=2)
    sub = ParagraphStyle("s", parent=estilos["Normal"], textColor=colors.HexColor("#64748B"), fontSize=9)
    celda = ParagraphStyle("c", parent=estilos["Normal"], fontSize=8, leading=10,
                           textColor=colors.HexColor("#1E293B"))
    celda_enc = ParagraphStyle("h", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")

    def esc(valor: Any) -> str:
        t = "" if valor in (None, "") else str(valor)
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def p(valor: Any, est=celda) -> Paragraph:
        return Paragraph(esc(valor) or "—", est)

    historia: list = [
        Paragraph("Lista de medicamentos", titulo),
        Paragraph(
            f"{esc(clinica_nombre)} · Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
            f"{len(medicamentos)} registro(s)" + (f" · Filtro: {esc(filtro)}" if filtro else ""),
            sub,
        ),
        Spacer(1, 10),
    ]

    encabezados = ["#", "Nombre", "Principio activo", "Presentación", "Categoría", "Tipo",
                   "Receta", "Stock mín.", "Stock", "Código de barras"]
    anchos = [1.0, 5.2, 4.2, 4.6, 3.0, 2.2, 1.6, 1.8, 1.5, 3.4]  # cm (suman ≈ 28.5 cm útiles)
    datos = [[p(h, celda_enc) for h in encabezados]]
    for i, m in enumerate(medicamentos, start=1):
        datos.append([
            p(i), p(m.get("nombre")), p(m.get("principio_activo")), p(m.get("presentacion")),
            p(m.get("categoria")), p((m.get("tipo_articulo") or "medicamento").capitalize()),
            p("Sí" if m.get("requiere_receta") else "No"), p(m.get("stock_minimo") or 0),
            p(m.get("stock_actual") or 0), p(m.get("codigo_barras")),
        ])
    if len(datos) == 1:
        datos.append([p("")] * 1 + [p("Sin medicamentos registrados")] + [p("")] * 8)

    tabla = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{VERDE}")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(f"#{GRIS_BORDE}")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for fila in range(2, len(datos), 2):
        estilo.append(("BACKGROUND", (0, fila), (-1, fila), colors.HexColor("#F8FAFC")))
    tabla.setStyle(TableStyle(estilo))
    historia.append(tabla)

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        ancho, _ = landscape(A4)
        canvas.drawString(1.4 * cm, 0.9 * cm, "VITALIA · Lista de medicamentos · Confidencial")
        canvas.drawRightString(ancho - 1.4 * cm, 0.9 * cm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
