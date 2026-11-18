"""PDF de la receta con la leyenda de firma SIMULADA y el QR de validación (reportlab)."""
import io
from datetime import timezone
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LEYENDA = "FIRMA ELECTRÓNICA SIMULADA - USO ACADÉMICO - SIN VALIDEZ JURÍDICA"
VERDE = colors.HexColor("#247F76")
AMBAR_FONDO = colors.HexColor("#FFF3C4")
AMBAR_BORDE = colors.HexColor("#B7791F")
AMBAR_TEXTO = colors.HexColor("#6B4200")
GRIS = colors.HexColor("#5B6B67")
LINEA = colors.HexColor("#CFE0DC")

_ESTILOS = getSampleStyleSheet()
_NORMAL = ParagraphStyle("n", parent=_ESTILOS["Normal"], fontName="Helvetica", fontSize=9.5, leading=12.5)
_PEQUENO = ParagraphStyle("p", parent=_NORMAL, fontSize=8, leading=10, textColor=GRIS)
_CELDA = ParagraphStyle("c", parent=_NORMAL, fontSize=8.5, leading=10.5)
_CELDA_H = ParagraphStyle("ch", parent=_CELDA, fontName="Helvetica-Bold", textColor=colors.white)
_SECCION = ParagraphStyle("s", parent=_NORMAL, fontName="Helvetica-Bold", fontSize=10.5, textColor=VERDE, spaceBefore=8, spaceAfter=3)
_URL = ParagraphStyle("u", parent=_PEQUENO, fontSize=7.5, leading=9, wordWrap="CJK")


def _p(texto, estilo=_NORMAL) -> Paragraph:
    return Paragraph(escape(str(texto)) if texto not in (None, "") else "—", estilo)


def _fecha_utc_y_local(fecha) -> tuple[str, str]:
    utc = fecha.replace(tzinfo=timezone.utc)
    local = utc.astimezone()
    return utc.strftime("%d/%m/%Y %H:%M:%S UTC"), local.strftime("%d/%m/%Y %H:%M:%S (UTC%z)")


def _qr(valor: str, tamano: float) -> Drawing:
    widget = QrCodeWidget(valor, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    dibujo = Drawing(tamano, tamano, transform=[tamano / (x2 - x1), 0, 0, tamano / (y2 - y1), 0, 0])
    dibujo.add(widget)
    return dibujo


def _marco_pagina(canvas, doc, ctx) -> None:
    """Encabezado, leyenda visible y pie en TODAS las páginas."""
    canvas.saveState()
    ancho, alto = LETTER
    # Banda de marca
    canvas.setFillColor(VERDE)
    canvas.rect(0, alto - 1.6 * cm, ancho, 1.6 * cm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(1.8 * cm, alto - 1.05 * cm, "VITALIA · Receta médica")
    canvas.setFont("Helvetica", 9.5)
    canvas.drawRightString(ancho - 1.8 * cm, alto - 1.05 * cm, f"Receta No. {ctx['receta_id']:06d}")
    # Leyenda de simulación (visible)
    canvas.setFillColor(AMBAR_FONDO)
    canvas.setStrokeColor(AMBAR_BORDE)
    canvas.setLineWidth(1)
    canvas.rect(1.8 * cm, alto - 2.75 * cm, ancho - 3.6 * cm, 0.9 * cm, stroke=1, fill=1)
    canvas.setFillColor(AMBAR_TEXTO)
    canvas.setFont("Helvetica-Bold", 9.6)
    canvas.drawCentredString(ancho / 2, alto - 2.4 * cm, LEYENDA)
    # Pie
    canvas.setStrokeColor(LINEA)
    canvas.line(1.8 * cm, 1.75 * cm, ancho - 1.8 * cm, 1.75 * cm)
    canvas.setFillColor(AMBAR_TEXTO)
    canvas.setFont("Helvetica-Bold", 7.6)
    canvas.drawCentredString(ancho / 2, 1.3 * cm, LEYENDA)
    canvas.setFillColor(GRIS)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(ancho / 2, 0.9 * cm, "Documento con fines académicos. Datos y llaves ficticios. No usar para dispensar medicamentos reales.")
    canvas.drawRightString(ancho - 1.8 * cm, 0.9 * cm, f"Pág. {doc.page}")
    canvas.restoreState()


def generar_pdf_receta_firmada(*, receta, items, nombre_paciente, identidad, identificador,
                               fecha_firma, url_verificacion) -> bytes:
    """Devuelve los bytes del PDF. Estos bytes son los que se firman (SHA-256)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=3.3 * cm, bottomMargin=2.2 * cm,
        title=f"Receta {receta.id_PK:06d} - firma electrónica simulada",
        author="VITALIA (simulación académica)",
        subject=LEYENDA,
        pageCompression=0,  # texto legible/verificable dentro del PDF
    )
    ctx = {"receta_id": receta.id_PK}
    ancho_util = LETTER[0] - 3.6 * cm
    utc, local = _fecha_utc_y_local(fecha_firma)
    emision = receta.creado_en.strftime("%d/%m/%Y %H:%M") if receta.creado_en else "—"

    historia = []

    # Médico (identidad ficticia)
    historia.append(Paragraph("Médico (identidad ficticia de prueba)", _SECCION))
    t_medico = Table(
        [
            [_p("Nombre", _PEQUENO), _p(identidad.nombre_ficticio)],
            [_p("Cédula (ficticia)", _PEQUENO), _p(identidad.cedula_ficticia)],
            [_p("Especialidad", _PEQUENO), _p(identidad.especialidad_ficticia)],
        ],
        colWidths=[3.6 * cm, ancho_util - 3.6 * cm],
    )
    t_medico.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
                                  ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    historia.append(t_medico)

    # Paciente
    historia.append(Paragraph("Paciente", _SECCION))
    t_pac = Table(
        [[_p("Nombre", _PEQUENO), _p(nombre_paciente)], [_p("Fecha de emisión", _PEQUENO), _p(emision)]],
        colWidths=[3.6 * cm, ancho_util - 3.6 * cm],
    )
    t_pac.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    historia.append(t_pac)

    # Medicamentos
    historia.append(Paragraph("Medicamentos recetados", _SECCION))
    filas = [[_p(h, _CELDA_H) for h in ("Medicamento", "Dosis", "Frecuencia", "Duración", "Cant.", "Vía / indicaciones")]]
    for it in sorted(items, key=lambda i: i.id_PK):
        med = it.medicamento
        nombre = (med.nombre if med else f"ID {it.medicamento_id_FK}") + (f" · {med.presentacion}" if med and med.presentacion else "")
        extra = " — ".join(x for x in (it.via_administracion, it.instrucciones) if x)
        filas.append([_p(nombre, _CELDA), _p(it.dosis, _CELDA), _p(it.frecuencia, _CELDA), _p(it.duracion, _CELDA),
                      _p(it.cantidad, _CELDA), _p(extra, _CELDA)])
    anchos = [5.0 * cm, 2.3 * cm, 2.4 * cm, 2.1 * cm, 1.2 * cm, ancho_util - 13.0 * cm]
    t_med = Table(filas, colWidths=anchos, repeatRows=1)
    t_med.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F8F6")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINEA), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    historia.append(t_med)
    historia.append(Spacer(1, 6 * mm))

    # Bloque de firma + QR (se mantiene junto)
    historia.append(Paragraph("Firma electrónica simulada", _SECCION))
    detalle = Table(
        [
            [_p("Identificador único", _PEQUENO), _p(identificador)],
            [_p("Fecha y hora de firma", _PEQUENO), _p(utc)],
            [Paragraph("&nbsp;", _PEQUENO), _p(f"Hora del servidor: {local}", _PEQUENO)],
            [_p("Algoritmo", _PEQUENO), _p("RSA-2048 · RSASSA-PSS · SHA-256")],
            [_p("Huella de clave pública", _PEQUENO), _p(identidad.huella_sha256[:32] + "…")],
        ],
        colWidths=[3.7 * cm, ancho_util - 3.7 * cm - 4.6 * cm],
    )
    detalle.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    columna_qr = Table(
        [[_qr(url_verificacion, 3.4 * cm)], [Paragraph("Escanee para validar la firma", ParagraphStyle("q", parent=_PEQUENO, alignment=TA_CENTER))]],
        colWidths=[4.4 * cm],
    )
    columna_qr.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    bloque = Table([[detalle, columna_qr]], colWidths=[ancho_util - 4.6 * cm, 4.6 * cm])
    bloque.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, VERDE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(bloque)
    historia.append(Spacer(1, 2 * mm))
    historia.append(Paragraph(f"Validación pública: {escape(url_verificacion)}", _URL))
    historia.append(Paragraph(
        "La firma digital se conserva separada de este PDF (firma desprendida) y se comprueba en la dirección anterior con la clave "
        "pública del médico de prueba. Si este documento se modifica después de firmarse, la validación lo mostrará como inválido.",
        _PEQUENO))

    doc.build(historia, onFirstPage=lambda c, d: _marco_pagina(c, d, ctx), onLaterPages=lambda c, d: _marco_pagina(c, d, ctx))
    return buffer.getvalue()
