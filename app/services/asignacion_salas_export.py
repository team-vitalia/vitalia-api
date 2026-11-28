"""Resumen de asignación de salas a doctores en Excel y PDF.

Recibe datos simples (diccionarios) para no depender de la base de datos:

    datos = {
        "salas":        [{"id", "nombre", "tipo", "piso", "estado"}],
        "doctores":     [{"id", "nombre", "especialidad"}],
        "asignaciones": [{"id_PK", "doctor_id", "doctor_nombre", "especialidad", "sala_id", "sala_nombre",
                          "sala_tipo", "sala_piso", "sala_estado", "dia_semana", "hora_inicio", "hora_fin"}],
    }

Los horarios se repiten cada semana (dia_semana: 0 = lunes ... 6 = domingo; None = todos los días) y un turno
puede cruzar la medianoche (23:00 → 04:00), por eso el resumen semanal reparte cada turno en sus tramos.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import CondPageBreak, HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.horarios_sala import MIN_DIA, a_min, cruza_medianoche, duracion_min, tramos

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_CORTO = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

VERDE = "0F4C45"
VERDE_CLARO = "E6F4F1"
GRIS_BORDE = "CBD5E1"
GRIS_ZEBRA = "F8FAFC"
GRIS_TEXTO = "1E293B"

# Turnos para clasificar un horario (minutos desde las 00:00)
_TURNOS = (
    ("Matutino", [(7 * 60, 15 * 60)]),
    ("Vespertino", [(15 * 60, 23 * 60)]),
    ("Nocturno", [(0, 7 * 60), (23 * 60, MIN_DIA)]),
)


def _hhmm(t) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _turno(ini, fin) -> str:
    segs = tramos(None, ini, fin)
    nombres = [n for n, rangos in _TURNOS if any(s[1] < b and a < s[2] for s in segs for a, b in rangos)]
    return " + ".join(nombres) or "—"


def _dia_txt(d: int | None) -> str:
    return "Todos los días" if d is None else DIAS[d]


def _filas(datos: dict[str, Any]) -> list[dict[str, Any]]:
    """Una fila por asignación, ordenada por sala, día y hora."""
    out = []
    for a in datos.get("asignaciones", []):
        ini, fin = a["hora_inicio"], a["hora_fin"]
        dur = duracion_min(ini, fin) / 60
        out.append({
            "sala": a.get("sala_nombre") or f"Sala #{a['sala_id']}",
            "sala_id": a["sala_id"],
            "tipo": a.get("sala_tipo") or "",
            "piso": a.get("sala_piso") or "",
            "doctor": a.get("doctor_nombre") or f"Doctor #{a['doctor_id']}",
            "doctor_id": a["doctor_id"],
            "especialidad": a.get("especialidad") or "",
            "dia": a.get("dia_semana"),
            "dia_txt": _dia_txt(a.get("dia_semana")),
            "ini": _hhmm(ini),
            "fin": _hhmm(fin),
            "horas": round(dur, 2),
            "horas_semana": round(dur * (7 if a.get("dia_semana") is None else 1), 2),
            "cruza": cruza_medianoche(ini, fin),
            "turno": _turno(ini, fin),
            "_ini": ini,
            "_fin": fin,
        })
    out.sort(key=lambda r: (r["sala"].lower(), -1 if r["dia"] is None else r["dia"], r["ini"], r["doctor"].lower()))
    return out


def _semana(datos: dict[str, Any], por: str) -> dict[int, list[list[str]]]:
    """{id_de_sala_o_doctor: [lista de textos por día (0..6)]} con los tramos de cada día."""
    res: dict[int, list[list[tuple[int, str]]]] = {}
    for a in datos.get("asignaciones", []):
        clave = a["sala_id"] if por == "sala" else a["doctor_id"]
        otro = (a.get("doctor_nombre") or f"Doctor #{a['doctor_id']}") if por == "sala" else (a.get("sala_nombre") or f"Sala #{a['sala_id']}")
        ini, fin = a["hora_inicio"], a["hora_fin"]
        dias = res.setdefault(clave, [[] for _ in range(7)])
        for dia, i, f in tramos(a.get("dia_semana"), ini, fin):
            objetivo = range(7) if dia is None else [dia]
            continua = i == 0 and cruza_medianoche(ini, fin) and a_min(ini) > 0
            etiqueta = f"{i // 60:02d}:{i % 60:02d}–{('24:00' if f >= MIN_DIA else f'{f // 60:02d}:{f % 60:02d}')}"
            if continua:
                etiqueta += " (viene de ayer)"
            elif cruza_medianoche(ini, fin) and f >= MIN_DIA and a_min(fin) > 0:
                etiqueta += " (sigue mañana)"
            for d in objetivo:
                dias[d].append((i, f"{etiqueta}  {otro}"))
    return {k: [[t for _, t in sorted(dia)] for dia in v] for k, v in res.items()}


def _kpis(datos: dict[str, Any], filas: list[dict[str, Any]]) -> list[tuple[str, str]]:
    salas_con = {f["sala_id"] for f in filas}
    docs_con = {f["doctor_id"] for f in filas}
    total_salas = len(datos.get("salas", []))
    total_docs = len(datos.get("doctores", []))
    return [
        ("Asignaciones registradas", str(len(filas))),
        ("Salas con horarios", f"{len(salas_con)} de {total_salas}"),
        ("Doctores con sala", f"{len(docs_con)} de {total_docs}"),
        ("Horas de sala por semana", f"{round(sum(f['horas_semana'] for f in filas), 1)} h"),
    ]


def _encabezados_dia(semana_inicio: date | None) -> list[str]:
    if not semana_inicio:
        return DIAS_CORTO[:]
    return [f"{DIAS_CORTO[i]} {(semana_inicio + timedelta(days=i)).strftime('%d/%m')}" for i in range(7)]


def _subtitulo(semana_inicio: date | None) -> str:
    if not semana_inicio:
        return "Horarios semanales (se repiten cada semana)"
    fin = semana_inicio + timedelta(days=6)
    return f"Semana del {semana_inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')} · los horarios se repiten cada semana"


def _sin_asignar(datos: dict[str, Any], filas: list[dict[str, Any]]):
    salas_con = {f["sala_id"] for f in filas}
    docs_con = {f["doctor_id"] for f in filas}
    return (
        [s for s in datos.get("salas", []) if s["id"] not in salas_con],
        [d for d in datos.get("doctores", []) if d["id"] not in docs_con],
    )


# ====================================================================== EXCEL
def a_excel(datos: dict[str, Any], clinica_nombre: str = "Clínica VITALIA", semana_inicio: date | None = None) -> bytes:
    filas = _filas(datos)
    cabeceras_dia = _encabezados_dia(semana_inicio)

    borde = Border(*(Side(style="thin", color=GRIS_BORDE) for _ in range(4)))
    relleno_cab = PatternFill("solid", fgColor=VERDE)
    fuente_cab = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fuente = Font(name="Calibri", size=10)
    negrita = Font(name="Calibri", size=10, bold=True)
    zebra = PatternFill("solid", fgColor=GRIS_ZEBRA)
    ocupado = PatternFill("solid", fgColor=VERDE_CLARO)

    def titulo(ws, texto: str, sub: str, ancho: int):
        ws["A1"] = f"VITALIA · {clinica_nombre.upper()}"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color=VERDE)
        ws["A2"] = f"{texto} | {sub}"
        ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")
        ws["A3"] = f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        ws["A3"].font = Font(name="Calibri", size=9, color="64748B")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ancho)

    def cabecera(ws, fila: int, nombres: list[str]):
        for i, n in enumerate(nombres, start=1):
            c = ws.cell(row=fila, column=i, value=n)
            c.font, c.fill, c.border = fuente_cab, relleno_cab, borde
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[fila].height = 24

    def anchos(ws, lista: list[float]):
        for i, w in enumerate(lista, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    wb = Workbook()

    # --- 1) Resumen
    ws = wb.active
    ws.title = "Resumen"
    titulo(ws, "Resumen de asignación de salas", _subtitulo(semana_inicio), 4)
    for i, (k, v) in enumerate(_kpis(datos, filas), start=5):
        a, b = ws.cell(row=i, column=1, value=k), ws.cell(row=i, column=2, value=v)
        a.font, b.font = negrita, fuente
        a.border = b.border = borde
        a.fill = ocupado
    sin_salas, sin_docs = _sin_asignar(datos, filas)
    fila = 10
    ws.cell(row=fila, column=1, value="Salas sin horarios asignados").font = negrita
    for s in sin_salas or [{"nombre": "— ninguna —", "tipo": "", "piso": ""}]:
        fila += 1
        ws.cell(row=fila, column=1, value=s["nombre"]).font = fuente
        ws.cell(row=fila, column=2, value=" · ".join(x for x in (s.get("tipo"), f"Piso {s['piso']}" if s.get("piso") else "") if x)).font = fuente
    fila += 2
    ws.cell(row=fila, column=1, value="Doctores sin sala asignada").font = negrita
    for d in sin_docs or [{"nombre": "— ninguno —", "especialidad": ""}]:
        fila += 1
        ws.cell(row=fila, column=1, value=d["nombre"]).font = fuente
        ws.cell(row=fila, column=2, value=d.get("especialidad") or "").font = fuente
    anchos(ws, [38, 34, 14, 14])

    # --- 2) Asignaciones (detalle)
    ws = wb.create_sheet("Asignaciones")
    titulo(ws, "Detalle de asignaciones", _subtitulo(semana_inicio), 11)
    cols = ["Sala", "Tipo", "Piso", "Doctor", "Especialidad", "Día", "Inicio", "Fin", "Horas por turno", "Turno", "Cruza medianoche"]
    cabecera(ws, 5, cols)
    for r, f in enumerate(filas, start=6):
        vals = [f["sala"], f["tipo"], f["piso"], f["doctor"], f["especialidad"], f["dia_txt"], f["ini"], f["fin"], f["horas"], f["turno"], "Sí (termina al día siguiente)" if f["cruza"] else "No"]
        for c, v in enumerate(vals, start=1):
            cel = ws.cell(row=r, column=c, value=v)
            cel.font, cel.border = fuente, borde
            cel.alignment = Alignment(vertical="center", horizontal="center" if c in (3, 6, 7, 8, 9, 10) else "left", wrap_text=True)
            if r % 2 == 0:
                cel.fill = zebra
    if not filas:
        ws.cell(row=6, column=1, value="Aún no hay salas asignadas a doctores.").font = fuente
    anchos(ws, [24, 16, 8, 30, 24, 16, 9, 9, 14, 22, 28])
    ws.freeze_panes = "A6"
    if filas:
        ws.auto_filter.ref = f"A5:{get_column_letter(len(cols))}{5 + len(filas)}"

    # --- 3 y 4) Semana por sala / por doctor
    for nombre_hoja, por, lista in (("Semana por sala", "sala", datos.get("salas", [])), ("Semana por doctor", "doctor", datos.get("doctores", []))):
        ws = wb.create_sheet(nombre_hoja)
        titulo(ws, nombre_hoja, _subtitulo(semana_inicio), 8)
        cabecera(ws, 5, ["Sala" if por == "sala" else "Doctor"] + cabeceras_dia)
        semana = _semana(datos, por)
        for r, item in enumerate(lista, start=6):
            ws.cell(row=r, column=1, value=item["nombre"]).font = negrita
            ws.cell(row=r, column=1).border = borde
            ws.cell(row=r, column=1).alignment = Alignment(vertical="center", wrap_text=True)
            dias = semana.get(item["id"], [[] for _ in range(7)])
            altura = 20
            for d in range(7):
                cel = ws.cell(row=r, column=2 + d, value="\n".join(dias[d]) if dias[d] else "—")
                cel.font = fuente if dias[d] else Font(name="Calibri", size=10, color="94A3B8")
                cel.border = borde
                cel.alignment = Alignment(vertical="top", horizontal="left" if dias[d] else "center", wrap_text=True)
                if dias[d]:
                    cel.fill = ocupado
                    altura = max(altura, 15 * len(dias[d]) + 6)
            ws.row_dimensions[r].height = min(altura, 160)
        anchos(ws, [26] + [27] * 7)
        ws.freeze_panes = "B6"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ====================================================================== PDF
def a_pdf(datos: dict[str, Any], clinica_nombre: str = "Clínica VITALIA", semana_inicio: date | None = None) -> bytes:
    from app.services.reporte_export import NumberedCanvas, _buscar_logo_disco  # mismo pie de página corporativo

    filas = _filas(datos)
    c_verde = colors.HexColor(f"#{VERDE}")
    c_borde = colors.HexColor(f"#{GRIS_BORDE}")
    c_zebra = colors.HexColor(f"#{GRIS_ZEBRA}")
    c_ocupado = colors.HexColor(f"#{VERDE_CLARO}")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.8 * cm,
        title="VITALIA - Resumen de asignación de salas",
    )
    est = getSampleStyleSheet()
    s_titulo = ParagraphStyle("TitAS", parent=est["Title"], fontSize=18, leading=22, textColor=c_verde, alignment=0)
    s_sub = ParagraphStyle("SubAS", parent=est["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#475569"))
    s_h2 = ParagraphStyle("H2AS", parent=est["Heading2"], fontSize=12.5, textColor=c_verde, spaceBefore=10, spaceAfter=6)
    s_th = ParagraphStyle("THAS", parent=est["Normal"], fontSize=8.5, leading=11, fontName="Helvetica-Bold", textColor=colors.white, alignment=1)
    s_td = ParagraphStyle("TDAS", parent=est["Normal"], fontSize=7.5, leading=9.5, textColor=colors.HexColor(f"#{GRIS_TEXTO}"))
    s_td_b = ParagraphStyle("TDBAS", parent=s_td, fontName="Helvetica-Bold", fontSize=8)
    s_kpi_v = ParagraphStyle("KV", parent=est["Normal"], fontSize=15, leading=18, fontName="Helvetica-Bold", textColor=c_verde, alignment=1)
    s_kpi_k = ParagraphStyle("KK", parent=est["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#475569"), alignment=1)

    def esc(t: str) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    el: list = []
    logo = _buscar_logo_disco()
    if logo:
        el.append(Image(logo, width=32, height=32))
    el.append(Paragraph(f"<b>VITALIA</b> · {esc(clinica_nombre)}", s_titulo))
    el.append(Paragraph(f"<b>Resumen de asignación de salas a doctores</b> &nbsp;|&nbsp; {esc(_subtitulo(semana_inicio))}", s_sub))
    el.append(Paragraph(f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_sub))
    el.append(Spacer(1, 6))
    el.append(HRFlowable(width="100%", thickness=1.2, color=c_verde))
    el.append(Spacer(1, 8))

    # KPIs
    kp = _kpis(datos, filas)
    t = Table([[Paragraph(v, s_kpi_v) for _, v in kp], [Paragraph(k, s_kpi_k) for k, _ in kp]], colWidths=[6.675 * cm] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, c_borde), ("INNERGRID", (0, 0), (-1, -1), 0.4, c_borde),
        ("BACKGROUND", (0, 0), (-1, -1), c_ocupado), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)

    # Semana por sala y por doctor (matriz con nombres)
    ancho_total = 26.7 * cm
    for titulo_tabla, por, lista in (("Semana por sala", "sala", datos.get("salas", [])), ("Semana por doctor", "doctor", datos.get("doctores", []))):
        if not lista:
            continue
        semana = _semana(datos, por)
        cab = [Paragraph("Sala" if por == "sala" else "Doctor", s_th)] + [Paragraph(h, s_th) for h in _encabezados_dia(semana_inicio)]
        data = [cab]
        estilos = []
        for r, item in enumerate(lista, start=1):
            sub = item.get("especialidad") if por == "doctor" else " · ".join(x for x in (item.get("tipo"), f"Piso {item['piso']}" if item.get("piso") else "") if x)
            fila = [Paragraph(f"<b>{esc(item['nombre'])}</b>" + (f"<br/><font size=6.5 color='#64748B'>{esc(sub)}</font>" if sub else ""), s_td)]
            dias = semana.get(item["id"], [[] for _ in range(7)])
            for d in range(7):
                if dias[d]:
                    fila.append([Paragraph(esc(x), s_td) for x in dias[d]])
                    estilos.append(("BACKGROUND", (1 + d, r), (1 + d, r), c_ocupado))
                else:
                    fila.append(Paragraph("<font color='#94A3B8'>—</font>", s_td))
            data.append(fila)
        tabla = Table(data, colWidths=[4.2 * cm] + [(ancho_total - 4.2 * cm) / 7] * 7, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_verde), ("GRID", (0, 0), (-1, -1), 0.4, c_borde),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), *estilos,
        ]))
        el.append(Paragraph(titulo_tabla, s_h2))
        el.append(tabla)

    # Detalle (si queda poco espacio en la página, el título pasa a la siguiente junto con la tabla)
    el.append(CondPageBreak(5 * cm))
    el.append(Paragraph("Detalle de asignaciones", s_h2))
    if filas:
        cab = [Paragraph(h, s_th) for h in ("Sala", "Doctor", "Especialidad", "Día", "Horario", "Horas", "Turno")]
        data = [cab]
        for f in filas:
            horario = f"{f['ini']} – {f['fin']}" + (" (+1 día)" if f["cruza"] else "")
            data.append([Paragraph(esc(x), s_td) for x in (f["sala"], f["doctor"], f["especialidad"] or "—", f["dia_txt"], horario, f"{f['horas']:g} h", f["turno"])])
        tabla = Table(data, colWidths=[4.6 * cm, 5.6 * cm, 3.8 * cm, 2.8 * cm, 3.6 * cm, 1.8 * cm, 4.5 * cm], repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_verde), ("GRID", (0, 0), (-1, -1), 0.4, c_borde),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_zebra]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        el.append(tabla)
    else:
        el.append(Paragraph("Aún no hay salas asignadas a doctores.", s_sub))

    # Pendientes
    sin_salas, sin_docs = _sin_asignar(datos, filas)
    if sin_salas or sin_docs:
        el.append(Paragraph("Pendientes por asignar", s_h2))
        if sin_salas:
            el.append(Paragraph("<b>Salas sin horarios:</b> " + esc(", ".join(s["nombre"] for s in sin_salas)), s_sub))
        if sin_docs:
            el.append(Paragraph("<b>Doctores sin sala:</b> " + esc(", ".join(d["nombre"] for d in sin_docs)), s_sub))

    doc.build(el, canvasmaker=NumberedCanvas)
    return buf.getvalue()
