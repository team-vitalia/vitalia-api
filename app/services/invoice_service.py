import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generar_pdf_factura(
    folio: str,
    fecha: str,
    nombre_clinica: str,
    nombre_admin: str,
    correo: str,
    nombre_plan: str,
    precio_mensual: float,
    subscription_id: str,
    es_upgrade: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0F766E")
    c_dark = colors.HexColor("#134E4A")
    c_light_bg = colors.HexColor("#F8FAFC")
    c_teal_bg = colors.HexColor("#F0FDFA")
    c_border_light = colors.HexColor("#E2E8F0")
    c_text = colors.HexColor("#1E293B")
    c_muted = colors.HexColor("#64748B")

    sub_company = ParagraphStyle(
        "SubCompany",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=c_muted,
        leading=12,
    )
    sub_doc = ParagraphStyle(
        "SubDoc",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=c_muted,
        alignment=2,
        leading=12,
    )
    sec_title = ParagraphStyle(
        "SecTitle",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=c_dark,
        leading=12,
    )
    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=c_text,
        leading=12,
    )
    th_style = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        leading=10,
    )
    td_style = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=c_text,
        leading=11,
    )
    td_right = ParagraphStyle(
        "TDRight",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=c_text,
        alignment=2,
        leading=11,
    )
    td_right_bold = ParagraphStyle(
        "TDRightBold",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=c_dark,
        alignment=2,
        leading=11,
    )

    subtotal = round(precio_mensual / 1.16, 2)
    iva = round(precio_mensual - subtotal, 2)
    total = precio_mensual

    tipo_concepto = (
        "Actualización de Plan" if es_upgrade else "Alta de Suscripción Inicial"
    )

    header_data = [
        [
            Paragraph(
                "<b>VITALIA HEALTHCARE SAAS</b><br/>"
                "Vitalia S.A. de C.V.<br/>"
                "RFC: VIT240815SA1<br/>"
                "Av.Carretera del Departamento del D.F. km 7.5, Ejido de Santa María Atarasquillo, Lerma, Estado de México.<br/>"
                "vitaliaorg98@gmail.com | www.vitalia.software",
                sub_company,
            ),
            Paragraph(
                "<b>COMPROBANTE / FACTURA DE SUSCRIPCIÓN</b><br/>"
                f"<b>Folio:</b> {folio}<br/>"
                f"<b>Fecha:</b> {fecha}<br/>"
                "<b>Moneda:</b> MXN - Peso Mexicano<br/>"
                "<b>Forma de Pago:</b> Pago electrónico en línea (PayPal)",
                sub_doc,
            ),
        ]
    ]
    t_header = Table(header_data, colWidths=[310, 230])
    t_header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    client_data = [
        [
            Paragraph("<b>DATOS DEL CLIENTE / RECEPTOR</b>", sec_title),
            Paragraph("<b>DETALLES DE LA TRANSACCIÓN</b>", sec_title),
        ],
        [
            Paragraph(
                f"<b>Clínica:</b> {nombre_clinica}<br/>"
                f"<b>Titular / Administrador:</b> {nombre_admin}<br/>"
                f"<b>Correo Electrónico:</b> {correo}",
                meta_val,
            ),
            Paragraph(
                f"<b>ID Suscripción PayPal:</b> {subscription_id}<br/>"
                f"<b>Plan Activado:</b> Plan {nombre_plan}<br/>"
                f"<b>Tipo de Operación:</b> {tipo_concepto}<br/>"
                "<b>Estado:</b> PAGADO / ACTIVO",
                meta_val,
            ),
        ],
    ]
    t_client = Table(client_data, colWidths=[270, 270])
    t_client.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), c_light_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, c_border_light),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border_light),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    items_data = [
        [
            Paragraph("CANT", th_style),
            Paragraph("CONCEPTO / DESCRIPCIÓN", th_style),
            Paragraph("PLAN", th_style),
            Paragraph("PRECIO UNIT.", th_style),
            Paragraph("IMPORTE", th_style),
        ],
        [
            Paragraph("1", td_style),
            Paragraph(
                f"Suscripción Mensual a Vitalia SaaS ({tipo_concepto})",
                td_style,
            ),
            Paragraph(nombre_plan, td_style),
            Paragraph(f"${subtotal:,.2f}", td_right),
            Paragraph(f"${subtotal:,.2f}", td_right),
        ],
    ]
    t_items = Table(items_data, colWidths=[40, 240, 80, 90, 90])
    t_items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, c_border_light),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ]
        )
    )

    totals_data = [
        [Paragraph("Subtotal:", td_right_bold), Paragraph(f"${subtotal:,.2f} MXN", td_right)],
        [Paragraph("IVA Trasladado (16%):", td_right_bold), Paragraph(f"${iva:,.2f} MXN", td_right)],
        [Paragraph("<b>Total Pagado:</b>", td_right_bold), Paragraph(f"<b>${total:,.2f} MXN</b>", td_right_bold)],
    ]
    t_totals = Table(totals_data, colWidths=[420, 120])
    t_totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 2), (1, 2), 1, c_primary),
            ]
        )
    )

    stamp_data = [
        [
            Paragraph(
                "<b>ESTATUS DEL PAGO: APROBADO Y CONFIRMADO</b><br/>"
                f"Suscripción vinculada exitosamente con PayPal (ID: {subscription_id}). "
                "Los módulos y capacidades correspondientes a su plan han sido activados en el sistema VITALIA.",
                sub_company,
            )
        ]
    ]
    t_stamp = Table(stamp_data, colWidths=[540])
    t_stamp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), c_teal_bg),
                ("BOX", (0, 0), (-1, -1), 1, c_primary),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    footer_p = Paragraph(
        "Vitalia Healthcare Software S.A. de C.V. &bull; www.vitalia.software &bull; vitaliaorg98@gmail.com<br/>"
        "Comprobante digital de servicio en la nube emitido de conformidad con las disposiciones aplicables.",
        sub_company,
    )

    story = [
        t_header,
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceBefore=0, spaceAfter=10),
        t_client,
        Spacer(1, 12),
        t_items,
        Spacer(1, 8),
        t_totals,
        Spacer(1, 14),
        t_stamp,
        Spacer(1, 16),
        footer_p,
    ]

    doc.build(story)
    return buffer.getvalue()
