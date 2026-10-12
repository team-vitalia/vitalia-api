from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import re
import unicodedata
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)


def obtener_nombre_carpeta(nombre: str) -> str:
    """Convierte el nombre del médico en un nombre de carpeta seguro."""
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^a-zA-Z0-9_-]+", "_", nombre)
    return nombre.strip("_") or "Medico"

def generar_pdf_contrato(contrato, doctor) -> str:
    # Raíz del proyecto vitalia-api
    raiz_proyecto = Path(__file__).resolve().parents[2]

    nombre_doctor = "Médico"
    if getattr(doctor, "usuario", None):
        nombre_doctor = doctor.usuario.nombre or "Médico"

    carpeta_doctor = obtener_nombre_carpeta(nombre_doctor)

    carpeta = (
        raiz_proyecto
        / "storage"
        / "contratos"
        / carpeta_doctor
    )
    carpeta.mkdir(parents=True, exist_ok=True)

    archivo = carpeta / f"contrato_{contrato.id_PK}.pdf"
    contenido = BytesIO()

    verde = colors.HexColor("#247F76")
    verde_oscuro = colors.HexColor("#185E57")
    gris = colors.HexColor("#404B49")
    gris_claro = colors.HexColor("#788581")

    documento = SimpleDocTemplate(
        contenido,
        pagesize=letter,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"Contrato de servicios médicos VITALIA {contrato.id_PK}",
        author="VITALIA",
    )

    estilos = getSampleStyleSheet()

    estilos.add(
        ParagraphStyle(
            name="Marca",
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=28,
            alignment=TA_CENTER,
            textColor=verde_oscuro,
            spaceAfter=4,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="Lema",
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            alignment=TA_CENTER,
            textColor=gris_claro,
            spaceAfter=18,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="TituloContrato",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=19,
            alignment=TA_CENTER,
            textColor=gris,
            spaceBefore=15,
            spaceAfter=8,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="NumeroContrato",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            alignment=TA_CENTER,
            textColor=gris_claro,
            spaceAfter=18,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="SeccionContrato",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=15,
            alignment=TA_LEFT,
            textColor=verde_oscuro,
            spaceBefore=15,
            spaceAfter=7,
            keepWithNext=True,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="TextoContrato",
            fontName="Helvetica",
            fontSize=9.5,
            leading=16,
            alignment=TA_JUSTIFY,
            textColor=gris,
            spaceAfter=10,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="PieContrato",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=gris_claro,
        )
    )

    def texto(valor, predeterminado="No especificado"):
        if valor is None or str(valor).strip() == "":
            valor = predeterminado
        return escape(str(valor))

    def fecha(valor):
        return valor.strftime("%d/%m/%Y") if valor else "No especificada"

    def moneda(valor):
        try:
            return f"${float(valor or 0):,.2f} MXN"
        except (TypeError, ValueError):
            return "No especificado"

    elementos = []

    # Encabezado institucional
    elementos.append(Paragraph("VITALIA", estilos["Marca"]))
    elementos.append(
        Paragraph(
            "SISTEMA DE GESTIÓN Y ADMINISTRACIÓN CLÍNICA",
            estilos["Lema"],
        )
    )

    elementos.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=verde,
            spaceBefore=2,
            spaceAfter=14,
        )
    )

    elementos.append(
        Paragraph(
            "CONTRATO DE PRESTACIÓN DE SERVICIOS MÉDICOS",
            estilos["TituloContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"Folio: VIT-{contrato.id_PK:05d}"
            f" &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Fecha de emisión: {date.today().strftime('%d/%m/%Y')}",
            estilos["NumeroContrato"],
        )
    )

    # Introducción
    elementos.append(
        Paragraph(
            "DOCUMENTO CONTRACTUAL",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            "El presente documento tiene por objeto identificar al "
            "profesional médico y describir las condiciones administrativas "
            "registradas en el sistema VITALIA en relación con su contrato. "
            "La información se presenta para su revisión y validación por "
            "las partes correspondientes.",
            estilos["TextoContrato"],
        )
    )

    # Primera sección
    elementos.append(
        Paragraph(
            "PRIMERA. IDENTIFICACIÓN DEL PROFESIONAL",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Nombre del profesional médico:</b> "
            f"{texto(nombre_doctor)}.",
            estilos["TextoContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Identificador de médico en el sistema:</b> "
            f"{texto(contrato.doctor_id_FK)}.",
            estilos["TextoContrato"],
        )
    )

    # Segunda sección
    elementos.append(
        Paragraph(
            "SEGUNDA. TIPO Y ESTADO DEL CONTRATO",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"El tipo de contrato registrado es "
            f"<b>{texto(contrato.tipo_contrato)}</b>. "
            f"Su estado administrativo actual en el sistema VITALIA es "
            f"<b>{texto(contrato.estado)}</b>.",
            estilos["TextoContrato"],
        )
    )

    # Tercera sección
    elementos.append(
        Paragraph(
            "TERCERA. VIGENCIA",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"La fecha de inicio registrada para el contrato es "
            f"<b>{fecha(contrato.fecha_inicio)}</b>. "
            f"La fecha de término registrada es "
            f"<b>{fecha(contrato.fecha_fin)}</b>. "
            "La vigencia deberá interpretarse conforme a las condiciones "
            "acordadas y a las disposiciones que resulten aplicables.",
            estilos["TextoContrato"],
        )
    )

    # Cuarta sección
    elementos.append(
        Paragraph(
            "CUARTA. REMUNERACIÓN",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            f"La cantidad registrada en el sistema como salario o "
            f"remuneración es de <b>{moneda(contrato.salario)}</b>. "
            "La periodicidad, forma de pago, deducciones y demás condiciones "
            "económicas deberán establecerse expresamente en el acuerdo "
            "correspondiente.",
            estilos["TextoContrato"],
        )
    )

    # Quinta sección
    elementos.append(
        Paragraph(
            "QUINTA. ACTUALIZACIÓN DE LA INFORMACIÓN",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            "Los datos descritos en este documento corresponden a la "
            "información almacenada en VITALIA. Cualquier modificación "
            "relativa al tipo de contrato, vigencia, estado o remuneración "
            "deberá actualizarse mediante los procedimientos autorizados "
            "por la administración correspondiente.",
            estilos["TextoContrato"],
        )
    )

    # Sexta sección
    elementos.append(
        Paragraph(
            "SEXTA. REVISIÓN Y VALIDACIÓN",
            estilos["SeccionContrato"],
        )
    )

    elementos.append(
        Paragraph(
            "El contenido de este documento deberá revisarse para confirmar "
            "que los datos sean correctos y que las condiciones contractuales "
            "se encuentren debidamente establecidas. La generación de este "
            "PDF por sí sola no acredita la aceptación ni la firma de las "
            "partes.",
            estilos["TextoContrato"],
        )
    )

    elementos.append(Spacer(1, 16))

    elementos.append(
        HRFlowable(
            width="100%",
            thickness=0.7,
            color=colors.HexColor("#D7E2DF"),
            spaceBefore=4,
            spaceAfter=10,
        )
    )

    elementos.append(
        Paragraph(
            "Documento generado por el sistema VITALIA para fines "
            "administrativos y de revisión contractual.",
            estilos["PieContrato"],
        )
    )

    # Pie de página y numeración
    def dibujar_pie(canvas, doc):
        canvas.saveState()

        ancho, _ = letter
        canvas.setStrokeColor(colors.HexColor("#D7E2DF"))
        canvas.setLineWidth(0.5)

        canvas.line(
            documento.leftMargin,
            0.55 * inch,
            ancho - documento.rightMargin,
            0.55 * inch,
        )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(gris_claro)

        canvas.drawString(
            documento.leftMargin,
            0.36 * inch,
            f"VITALIA | Folio VIT-{contrato.id_PK:05d}",
        )

        canvas.drawRightString(
            ancho - documento.rightMargin,
            0.36 * inch,
            f"Página {doc.page}",
        )

        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=dibujar_pie,
        onLaterPages=dibujar_pie,
    )

    archivo.write_bytes(contenido.getvalue())

    return archivo.relative_to(raiz_proyecto).as_posix()