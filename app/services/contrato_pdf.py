from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import re
import unicodedata

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
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

    # Obtener el nombre del médico
    nombre_doctor = "Medico"
    if getattr(doctor, "usuario", None):
        nombre_doctor = doctor.usuario.nombre or "Medico"

    # Crear una carpeta con el nombre del médico
    carpeta_doctor = obtener_nombre_carpeta(nombre_doctor)

    carpeta = (
        raiz_proyecto
        / "storage"
        / "contratos"
        / carpeta_doctor
    )
    carpeta.mkdir(parents=True, exist_ok=True)

    # Crear el archivo correspondiente al contrato
    archivo = carpeta / f"contrato_{contrato.id_PK}.pdf"

    def fecha(valor):
        return valor.strftime("%d/%m/%Y") if valor else "No especificada"

    def texto(valor):
        return escape(str(valor)) if valor is not None else "No especificado"

    contenido = BytesIO()

    documento = SimpleDocTemplate(
        contenido,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )

    estilos = getSampleStyleSheet()

    estilos.add(
        ParagraphStyle(
            name="TituloVitalia",
            parent=estilos["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#247F76"),
            fontSize=22,
            spaceAfter=8,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="SubtituloVitalia",
            parent=estilos["Normal"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#627772"),
            fontSize=11,
            spaceAfter=20,
        )
    )

    elementos = [
        Paragraph("VITALIA", estilos["TituloVitalia"]),
        Paragraph("CONTRATO MEDICO", estilos["SubtituloVitalia"]),
        Spacer(1, 10),
        Paragraph(
            f"<b>Numero de contrato:</b> {contrato.id_PK}",
            estilos["Normal"],
        ),
        Spacer(1, 16),
        Paragraph(
            "DATOS DEL MEDICO Y DEL CONTRATO",
            estilos["Heading2"],
        ),
        Spacer(1, 10),
    ]

    filas = [
        ["Campo", "Informacion"],
        ["Medico", texto(nombre_doctor)],
        ["Identificador del medico", str(contrato.doctor_id_FK)],
        ["Tipo de contrato", texto(contrato.tipo_contrato)],
        ["Estado", texto(contrato.estado)],
        ["Fecha de inicio", fecha(contrato.fecha_inicio)],
        ["Fecha de fin", fecha(contrato.fecha_fin)],
        [
            "Salario",
            f"${float(contrato.salario or 0):,.2f} MXN",
        ],
    ]

    tabla = Table(
        filas,
        colWidths=[2.2 * inch, 4.5 * inch],
    )

    tabla.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#247F76"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#DCE8E5"),
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (0, -1),
                    colors.HexColor("#EAF5F2"),
                ),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    elementos.append(tabla)
    elementos.append(Spacer(1, 35))
    elementos.append(
        Paragraph("FIRMAS", estilos["Heading2"])
    )
    elementos.append(Spacer(1, 45))

    firmas = Table(
        [
            ["____________________________", "____________________________"],
            ["Representante de VITALIA", texto(nombre_doctor)],
            ["Firma", "Firma del medico"],
        ],
        colWidths=[3.35 * inch, 3.35 * inch],
    )

    firmas.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elementos.append(firmas)

    # Generar el contenido del PDF
    documento.build(elementos)

    # Crear o reemplazar el PDF correspondiente al contrato
    archivo.write_bytes(contenido.getvalue())

    # Ruta relativa que se guardará en MySQL
    return archivo.relative_to(raiz_proyecto).as_posix()
