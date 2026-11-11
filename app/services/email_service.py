import asyncio
from datetime import datetime
import logging
import os
import resend

logger = logging.getLogger("vitalia.email_service")


def enviar_correo_sincrono(destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str = "", adjuntos: list[dict] = None) -> bool:
    if not destinatario or "@" not in destinatario:
        return False

    resend.api_key = os.environ.get("RESEND_API_KEY")
    if not resend.api_key:
        logger.warning(f"No se enviará correo a {destinatario}: RESEND_API_KEY no está configurada.")
        return False

    params = {
        "from": "notificaciones@vitalia.software",
        "to": [destinatario],
        "subject": asunto,
        "html": cuerpo_html,
    }
    if cuerpo_texto:
        params["text"] = cuerpo_texto
    if adjuntos:
        params["attachments"] = adjuntos

    try:
        resend.Emails.send(params)
        logger.info(f"Correo enviado correctamente a {destinatario} con asunto: {asunto}")
        return True
    except Exception as error:
        logger.warning(f"No fue posible enviar correo a {destinatario}: {error}")
        return False


async def enviar_correo(destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str = "", adjuntos: list[dict] = None) -> bool:
    return await asyncio.to_thread(
        enviar_correo_sincrono,
        destinatario,
        asunto,
        cuerpo_html,
        cuerpo_texto,
        adjuntos,
    )


def construir_plantilla_base(titulo: str, subtitulo_badge: str, color_badge_bg: str, color_badge_txt: str, filas_detalle: list[tuple[str, str]], mensaje_adicional: str, mostrar_recomendacion: bool = True, contenido_extra: str = "") -> str:
    detalles_html = ""
    for etiqueta, valor in filas_detalle:
        detalles_html += f"""
        <tr>
            <td style="padding: 10px 14px; border-bottom: 1px solid rgb(238, 244, 242); color: rgb(110, 130, 126); font-size: 13px; font-weight: 600; width: 35%;">{etiqueta}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid rgb(238, 244, 242); color: rgb(23, 63, 58); font-size: 14px; font-weight: 700;">{valor}</td>
        </tr>
        """

    recomendacion_html = """<div style="background-color: rgb(231, 245, 242); border-left: 4px solid rgb(36, 127, 118); padding: 14px 16px; border-radius: 0 10px 10px 0; margin-bottom: 26px;">
                    <div style="font-size: 13px; font-weight: 700; color: rgb(23, 104, 95); margin-bottom: 3px;">Recomendación de llegada</div>
                    <div style="font-size: 12px; color: rgb(63, 100, 94); line-height: 1.5;">
                        Por favor preséntate en la clínica 10 minutos antes del horario programado para registrar tu llegada en recepción.
                    </div>
                </div>""" if mostrar_recomendacion else ""

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titulo}</title>
</head>
<body style="margin: 0; padding: 24px; background-color: rgb(244, 250, 248); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" style="max-width: 600px; width: 100%; margin: 0 auto; background-color: rgb(255, 255, 255); border-radius: 20px; border: 1px solid rgb(226, 236, 234); overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.04);" cellpadding="0" cellspacing="0">
        <tr>
            <td style="background-color: rgb(36, 127, 118); padding: 28px 30px; text-align: center;">
                <div style="font-size: 26px; font-weight: 900; color: rgb(255, 255, 255); letter-spacing: 2px;">VITALIA</div>
                <div style="font-size: 12px; color: rgb(189, 229, 223); margin-top: 4px; letter-spacing: 0.5px;">Gestión clínica inteligente</div>
            </td>
        </tr>
        <tr>
            <td style="padding: 32px 30px;">
                <div style="display: inline-block; padding: 6px 14px; border-radius: 20px; background-color: {color_badge_bg}; color: {color_badge_txt}; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px;">
                    {subtitulo_badge}
                </div>
                <h1 style="margin: 0 0 12px 0; font-size: 22px; font-weight: 800; color: rgb(23, 63, 58); line-height: 1.3;">
                    {titulo}
                </h1>
                <p style="margin: 0 0 22px 0; font-size: 14px; color: rgb(85, 105, 101); line-height: 1.6;">
                    {mensaje_adicional}
                </p>

                <table style="width: 100%; border-collapse: separate; border-spacing: 0; background-color: rgb(250, 253, 252); border: 1px solid rgb(226, 238, 235); border-radius: 14px; overflow: hidden; margin-bottom: 24px;">
                    {detalles_html}
                </table>

                {recomendacion_html}
                {contenido_extra}

                <div style="border-top: 1px solid rgb(235, 242, 240); padding-top: 20px; text-align: center;">
                    <div style="font-size: 11px; color: rgb(154, 169, 166); line-height: 1.6;">
                        Este es un mensaje generado automáticamente por el sistema VITALIA.<br>
                        Si necesitas asistencia, contacta al área de recepción de la clínica.
                    </div>
                </div>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def generar_html_cita_agendada(paciente_nombre: str, doctor_nombre: str, fecha: str, hora_inicio: str, hora_fin: str, motivo: str) -> str:
    filas = [
        ("Paciente", paciente_nombre),
        ("Médico Asignado", f"Dr./Dra. {doctor_nombre}"),
        ("Fecha de Cita", fecha),
        ("Horario de Consulta", f"{hora_inicio} - {hora_fin}"),
        ("Motivo", motivo or "Consulta médica general"),
    ]
    return construir_plantilla_base(
        titulo="Tu cita médica ha sido confirmada",
        subtitulo_badge="Cita Agendada",
        color_badge_bg="rgb(231, 245, 242)",
        color_badge_txt="rgb(36, 127, 118)",
        filas_detalle=filas,
        mensaje_adicional=f"Hola {paciente_nombre}, tu cita médica ha sido registrada con éxito en nuestro sistema de atención clínica. A continuación encontrarás los detalles de tu consulta:"
    )


def html_enlace_recuperacion(nombre: str, enlace: str) -> str:
    enlace_html = (enlace.replace("&", "&amp;").replace('"', "&quot;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
    return construir_plantilla_base(
        titulo="Restablece tu contraseña",
        subtitulo_badge="Recuperación de contraseña",
        color_badge_bg="rgb(226, 244, 240)",
        color_badge_txt="rgb(36, 127, 118)",
        filas_detalle=[
            ("Usuario", nombre),
            ("Acceso", f'<a href="{enlace_html}">Cambiar mi contraseña</a>'),
            ("Vigencia", "10 minutos"),
        ],
        mensaje_adicional=(
            "Recibimos una solicitud para cambiar tu contraseña. Usa el enlace para establecer una nueva. "
            "Si no solicitaste este cambio, ignora este mensaje."
        ),
    )


def generar_html_cita_reprogramada(paciente_nombre: str, doctor_nombre: str, nueva_fecha: str, nueva_hora_inicio: str, nueva_hora_fin: str, motivo: str) -> str:
    filas = [
        ("Paciente", paciente_nombre),
        ("Médico Asignado", f"Dr./Dra. {doctor_nombre}"),
        ("Nueva Fecha", nueva_fecha),
        ("Nuevo Horario", f"{nueva_hora_inicio} - {nueva_hora_fin}"),
        ("Motivo", motivo or "Consulta médica general"),
    ]
    return construir_plantilla_base(
        titulo="Tu cita médica ha sido reprogramada",
        subtitulo_badge="Actualización de Agenda",
        color_badge_bg="rgb(254, 243, 199)",
        color_badge_txt="rgb(217, 119, 6)",
        filas_detalle=filas,
        mensaje_adicional=f"Hola {paciente_nombre}, te informamos que el horario de tu cita médica ha sido modificado. Por favor revisa la nueva fecha y hora asignadas:"
    )


def generar_html_recordatorio_cita(paciente_nombre: str, doctor_nombre: str, fecha: str, hora: str, intervalo_texto: str, motivo: str) -> str:
    filas = [
        ("Paciente", paciente_nombre),
        ("Médico Asignado", f"Dr./Dra. {doctor_nombre}"),
        ("Fecha Programada", fecha),
        ("Hora de Atención", hora),
        ("Aviso de Recordatorio", f"Falta {intervalo_texto}"),
        ("Motivo", motivo or "Consulta médica general"),
    ]
    return construir_plantilla_base(
        titulo=f"Recordatorio: Tu cita médica es en {intervalo_texto}",
        subtitulo_badge=f"Recordatorio ({intervalo_texto})",
        color_badge_bg="rgb(224, 242, 254)",
        color_badge_txt="rgb(2, 132, 199)",
        filas_detalle=filas,
        mensaje_adicional=f"Hola {paciente_nombre}, te recordamos que tienes una cita médica programada próximamente en VITALIA. Agradecemos tu puntualidad:"
    )


async def notificar_correo_cita_creada(destinatario: str, paciente_nombre: str, doctor_nombre: str, fecha: str, hora_inicio: str, hora_fin: str, motivo: str):
    if not destinatario:
        return
    asunto = f"Confirmación de Cita Médica - {fecha} {hora_inicio} - VITALIA"
    html = generar_html_cita_agendada(paciente_nombre, doctor_nombre, fecha, hora_inicio, hora_fin, motivo)
    texto = f"Cita Confirmada para {paciente_nombre} con Dr./Dra. {doctor_nombre} el día {fecha} de {hora_inicio} a {hora_fin}."
    await enviar_correo(destinatario, asunto, html, texto)


async def notificar_correo_cita_reprogramada(destinatario: str, paciente_nombre: str, doctor_nombre: str, nueva_fecha: str, nueva_hora_inicio: str, nueva_hora_fin: str, motivo: str):
    if not destinatario:
        return
    asunto = f"Actualización: Cita Médica Reprogramada - {nueva_fecha} {nueva_hora_inicio} - VITALIA"
    html = generar_html_cita_reprogramada(paciente_nombre, doctor_nombre, nueva_fecha, nueva_hora_inicio, nueva_hora_fin, motivo)
    texto = f"Cita Reprogramada para {paciente_nombre} con Dr./Dra. {doctor_nombre}. Nueva fecha: {nueva_fecha} de {nueva_hora_inicio} a {nueva_hora_fin}."
    await enviar_correo(destinatario, asunto, html, texto)


async def notificar_correo_recordatorio(destinatario: str, paciente_nombre: str, doctor_nombre: str, fecha: str, hora: str, intervalo_texto: str, motivo: str):
    if not destinatario:
        return
    asunto = f"Recordatorio: Tu Cita Médica es en {intervalo_texto} - VITALIA"
    html = generar_html_recordatorio_cita(paciente_nombre, doctor_nombre, fecha, hora, intervalo_texto, motivo)
    texto = f"Recordatorio de cita médica para {paciente_nombre} con Dr./Dra. {doctor_nombre} el {fecha} a las {hora}. Falta {intervalo_texto}."
    await enviar_correo(destinatario, asunto, html, texto)


def generar_html_bienvenida_admin(nombre_admin: str, nombre_clinica: str, url_pwa: str) -> str:
    filas = [
        ("Clínica", nombre_clinica),
        ("Administrador", nombre_admin),
        ("Acceso a la Plataforma", url_pwa),
        ("Estado", "Activo y Verificado"),
    ]
    return construir_plantilla_base(
        titulo="Bienvenido a VITALIA SaaS",
        subtitulo_badge="Suscripción Activada",
        color_badge_bg="rgb(220, 252, 231)",
        color_badge_txt="rgb(22, 101, 52)",
        filas_detalle=filas,
        mensaje_adicional=f"Estimado(a) {nombre_admin}, tu suscripción ha sido confirmada y la clínica {nombre_clinica} se encuentra lista para operar en VITALIA. Puedes ingresar a la plataforma médica a través del enlace de la PWA:"
    )


def enviar_correo_bienvenida_admin(
    destinatario: str,
    nombre_admin: str,
    nombre_clinica: str,
    url_pwa: str = "https://app.vitalia.software"
) -> bool:
    if not destinatario:
        return False
    asunto = f"Bienvenido a VITALIA - Clínica {nombre_clinica} Activada"
    html = generar_html_bienvenida_admin(nombre_admin, nombre_clinica, url_pwa)
    texto = f"Bienvenido a VITALIA. La clínica {nombre_clinica} ha sido activada con éxito. Accede a tu PWA en {url_pwa}."
    return enviar_correo_sincrono(destinatario, asunto, html, texto)


def generar_html_confirmacion_pago(
    nombre_admin: str,
    nombre_clinica: str,
    nombre_plan: str,
    precio_mensual: float,
    subscription_id: str,
    es_upgrade: bool = False,
    url_pwa: str = "https://app.vitalia.software",
) -> str:
    titulo = "Tu plan ha sido activado correctamente" if es_upgrade else "¡Bienvenido(a) a VITALIA SaaS!"
    subtitulo_badge = "Plan Actualizado" if es_upgrade else "Suscripción Activada"
    color_badge_bg = "rgb(224, 242, 254)" if es_upgrade else "rgb(220, 252, 231)"
    color_badge_txt = "rgb(2, 132, 199)" if es_upgrade else "rgb(22, 101, 52)"

    mensaje = (
        f"Estimado(a) <strong>{nombre_admin}</strong>, te confirmamos que la actualización de plan para la clínica "
        f"<strong>{nombre_clinica}</strong> ha sido activada con éxito. Ya puedes disfrutar de las nuevas capacidades habilitadas para tu equipo."
        if es_upgrade
        else
        f"Estimado(a) <strong>{nombre_admin}</strong>, te damos una cordial bienvenida a VITALIA. "
        f"Tu suscripción para la clínica <strong>{nombre_clinica}</strong> ha sido confirmada con éxito. "
        f"Ya cuentas con acceso a la plataforma para comenzar la gestión integral de tu centro médico."
    )

    filas = [
        ("Clínica", nombre_clinica),
        ("Administrador", nombre_admin),
        ("Plan Contratado", f"Plan {nombre_plan}"),
        ("Importe Mensual", f"${precio_mensual:,.2f} MXN"),
        ("ID Suscripción PayPal", subscription_id),
        ("Estado", "Activo y Verificado"),
    ]

    bloque_factura = f"""
    <div style="background-color: rgb(240, 253, 250); border: 1px solid rgb(204, 251, 241); padding: 16px 18px; border-radius: 12px; margin-bottom: 24px;">
        <div style="font-size: 13px; font-weight: 700; color: rgb(15, 118, 110); margin-bottom: 4px;">Comprobante de Pago / Factura</div>
        <div style="font-size: 12px; color: rgb(19, 78, 74); line-height: 1.5;">
            Hemos adjuntado a este correo tu factura oficial en formato PDF correspondiente al cargo de tu suscripción con PayPal.
        </div>
    </div>
    <div style="text-align: center; margin-bottom: 24px;">
        <a href="{url_pwa}" style="display: inline-block; background-color: rgb(15, 118, 110); color: rgb(255, 255, 255); font-size: 14px; font-weight: 700; text-decoration: none; padding: 12px 28px; border-radius: 12px;">Acceder a VITALIA</a>
    </div>
    """

    return construir_plantilla_base(
        titulo=titulo,
        subtitulo_badge=subtitulo_badge,
        color_badge_bg=color_badge_bg,
        color_badge_txt=color_badge_txt,
        filas_detalle=filas,
        mensaje_adicional=mensaje,
        mostrar_recomendacion=False,
        contenido_extra=bloque_factura,
    )


def enviar_correo_confirmacion_pago(
    destinatario: str,
    nombre_admin: str,
    nombre_clinica: str,
    nombre_plan: str,
    precio_mensual: float,
    subscription_id: str,
    es_upgrade: bool = False,
    url_pwa: str = "https://app.vitalia.software",
) -> bool:
    if not destinatario:
        return False

    asunto = "¡Gracias por su compra!"
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    sufijo_folio = subscription_id[-6:].upper() if len(subscription_id) >= 6 else "001"
    folio = f"F-{datetime.now().year}-{sufijo_folio}"

    from app.services.invoice_service import generar_pdf_factura

    pdf_bytes = generar_pdf_factura(
        folio=folio,
        fecha=fecha_emision,
        nombre_clinica=nombre_clinica,
        nombre_admin=nombre_admin,
        correo=destinatario,
        nombre_plan=nombre_plan,
        precio_mensual=precio_mensual,
        subscription_id=subscription_id,
        es_upgrade=es_upgrade,
    )

    html = generar_html_confirmacion_pago(
        nombre_admin=nombre_admin,
        nombre_clinica=nombre_clinica,
        nombre_plan=nombre_plan,
        precio_mensual=precio_mensual,
        subscription_id=subscription_id,
        es_upgrade=es_upgrade,
        url_pwa=url_pwa,
    )

    texto = (
        f"¡Gracias por su compra! La suscripción para {nombre_clinica} (Plan {nombre_plan}) ha sido "
        f"{'actualizada' if es_upgrade else 'activada'} exitosamente. Adjuntamos su factura en PDF."
    )

    adjuntos = [
        {
            "filename": f"Factura_Vitalia_{folio}.pdf",
            "content": list(pdf_bytes),
        }
    ]

    return enviar_correo_sincrono(destinatario, asunto, html, texto, adjuntos)


async def notificar_correo_confirmacion_pago(
    destinatario: str,
    nombre_admin: str,
    nombre_clinica: str,
    nombre_plan: str,
    precio_mensual: float,
    subscription_id: str,
    es_upgrade: bool = False,
    url_pwa: str = "https://app.vitalia.software",
) -> bool:
    return await asyncio.to_thread(
        enviar_correo_confirmacion_pago,
        destinatario,
        nombre_admin,
        nombre_clinica,
        nombre_plan,
        precio_mensual,
        subscription_id,
        es_upgrade,
        url_pwa,
    )
