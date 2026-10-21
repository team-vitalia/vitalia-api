import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

logger = logging.getLogger("vitalia.email_service")

def obtener_configuracion_smtp():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", os.getenv("SMTP_EMAIL", "")).strip()
    raw_pass = os.getenv("SMTP_PASSWORD", os.getenv("SMTP_PASS", "")).strip()
    password = raw_pass.replace(" ", "") if host == "smtp.gmail.com" else raw_pass
    from_addr = os.getenv("SMTP_FROM", user or "vitaliaorg98@gmail.com").strip()
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
    }

def enviar_correo_sincrono(destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str = "") -> bool:
    if not destinatario or "@" not in destinatario:
        return False

    config = obtener_configuracion_smtp()
    if not config["user"] or not config["password"]:
        logger.warning(f"No se enviará correo a {destinatario}: SMTP_USER o SMTP_PASSWORD no están configurados en el archivo .env.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = config["from_addr"]
    msg["To"] = destinatario

    if cuerpo_texto:
        msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    server = None
    try:
        server = smtplib.SMTP(config["host"], config["port"], timeout=12)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config["user"], config["password"])
        server.sendmail(config["from_addr"], [destinatario], msg.as_string())
        logger.info(f"Correo enviado correctamente a {destinatario} con asunto: {asunto}")
        return True
    except smtplib.SMTPAuthenticationError as auth_err:
        logger.warning(f"Error de autenticación SMTP al enviar a {destinatario}: Verifique que SMTP_USER sea correcto y que SMTP_PASSWORD sea una Contraseña de Aplicación de Google válida. Detalle: {auth_err}")
        return False
    except smtplib.SMTPServerDisconnected as disc_err:
        logger.warning(f"Error de conexión SMTP con {config['host']}: La conexión se cerró inesperadamente. En Gmail esto sucede cuando el usuario o la contraseña de aplicación de 16 caracteres son incorrectos o fueron revocados en Google. Detalle: {disc_err}")
        return False
    except Exception as error:
        logger.warning(f"No fue posible enviar correo SMTP a {destinatario}: {error}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

async def enviar_correo(destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str = "") -> bool:
    return await asyncio.to_thread(
        enviar_correo_sincrono,
        destinatario,
        asunto,
        cuerpo_html,
        cuerpo_texto,
    )

def construir_plantilla_base(titulo: str, subtitulo_badge: str, color_badge_bg: str, color_badge_txt: str, filas_detalle: list[tuple[str, str]], mensaje_adicional: str) -> str:
    detalles_html = ""
    for etiqueta, valor in filas_detalle:
        detalles_html += f"""
        <tr>
            <td style="padding: 10px 14px; border-bottom: 1px solid rgb(238, 244, 242); color: rgb(110, 130, 126); font-size: 13px; font-weight: 600; width: 35%;">{etiqueta}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid rgb(238, 244, 242); color: rgb(23, 63, 58); font-size: 14px; font-weight: 700;">{valor}</td>
        </tr>
        """

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

                <div style="background-color: rgb(231, 245, 242); border-left: 4px solid rgb(36, 127, 118); padding: 14px 16px; border-radius: 0 10px 10px 0; margin-bottom: 26px;">
                    <div style="font-size: 13px; font-weight: 700; color: rgb(23, 104, 95); margin-bottom: 3px;">Recomendación de llegada</div>
                    <div style="font-size: 12px; color: rgb(63, 100, 94); line-height: 1.5;">
                        Por favor preséntate en la clínica 10 minutos antes del horario programado para registrar tu llegada en recepción.
                    </div>
                </div>

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
