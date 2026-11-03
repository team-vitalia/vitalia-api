import json
import logging
import os
import smtplib
import time
import shutil
from http.client import HTTPException
from email.message import EmailMessage
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("vitalia.monitor")

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    logger.info("python-dotenv no disponible; se usarán variables del proceso.")


def enviar_correo(asunto: str, cuerpo: str) -> bool:
    destinatarios = [
        direccion.strip()
        for direccion in os.getenv("ALERT_EMAIL_TO", "").split(",")
        if direccion.strip()
    ]
    remitente = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")).strip()
    host = os.getenv("SMTP_HOST", "").strip()

    if not destinatarios or not remitente or not host:
        logger.error("Configura ALERT_EMAIL_TO, SMTP_FROM y SMTP_HOST para enviar alertas.")
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(cuerpo)

    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER", "").strip()
    contrasena = os.getenv("SMTP_PASSWORD", "")
    usar_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
    usar_starttls = os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}

    try:
        cliente_smtp = smtplib.SMTP_SSL if usar_ssl else smtplib.SMTP
        with cliente_smtp(host, puerto, timeout=15) as servidor:
            if not usar_ssl and usar_starttls:
                servidor.starttls()
            if usuario:
                servidor.login(usuario, contrasena)
            servidor.send_message(mensaje)
        logger.info("Alerta enviada por correo: %s", asunto)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("No se pudo enviar el correo de alerta.")
        return False


def comprobar_api(url: str, timeout: int) -> None:
    with urlopen(url, timeout=timeout) as respuesta:
        if respuesta.status != 200:
            raise RuntimeError(f"HTTP {respuesta.status}")
        contenido = json.loads(respuesta.read().decode("utf-8"))
        if contenido.get("status") != "ok":
            raise RuntimeError("La respuesta de /health no contiene status=ok")


def leer_cpu() -> tuple[int, int]:
    with open("/proc/stat", encoding="utf-8") as archivo:
        valores = [int(valor) for valor in archivo.readline().split()[1:]]
    return sum(valores), valores[3] + (valores[4] if len(valores) > 4 else 0)


def obtener_uso_cpu() -> float:
    total_inicial, inactivo_inicial = leer_cpu()
    time.sleep(1)
    total_final, inactivo_final = leer_cpu()
    total_delta = total_final - total_inicial
    if total_delta <= 0:
        return 0.0
    inactivo_delta = inactivo_final - inactivo_inicial
    return 100 * (1 - inactivo_delta / total_delta)


def obtener_uso_memoria() -> float:
    valores = {}
    with open("/proc/meminfo", encoding="utf-8") as archivo:
        for linea in archivo:
            clave, dato = linea.split(":", 1)
            if clave in {"MemTotal", "MemAvailable"}:
                valores[clave] = int(dato.strip().split()[0])
    total = valores["MemTotal"]
    disponible = valores["MemAvailable"]
    return 100 * (total - disponible) / total


def obtener_problemas() -> dict[str, str]:
    problemas = {}
    api_url = os.getenv("MONITOR_API_URL", "http://127.0.0.1:8000/health")
    timeout = int(os.getenv("MONITOR_HTTP_TIMEOUT_SECONDS", "8"))

    try:
        comprobar_api(api_url, timeout)
    except (HTTPException, OSError, RuntimeError, URLError, ValueError) as error:
        problemas["api_down"] = f"La comprobación de {api_url} falló: {error}"

    cpu = obtener_uso_cpu()
    memoria = obtener_uso_memoria()
    disco = shutil.disk_usage(os.getenv("MONITOR_DISK_PATH", "/")).used
    disco_total = shutil.disk_usage(os.getenv("MONITOR_DISK_PATH", "/")).total
    disco = 100 * disco / disco_total if disco_total else 0.0

    umbral_cpu = float(os.getenv("CPU_THRESHOLD_PERCENT", "85"))
    umbral_memoria = float(os.getenv("MEMORY_THRESHOLD_PERCENT", "90"))
    umbral_disco = float(os.getenv("DISK_THRESHOLD_PERCENT", "90"))

    if cpu >= umbral_cpu:
        problemas["high_cpu"] = f"CPU al {cpu:.1f}% (umbral: {umbral_cpu:.1f}%)."
    if memoria >= umbral_memoria:
        problemas["high_memory"] = f"Memoria al {memoria:.1f}% (umbral: {umbral_memoria:.1f}%)."
    if disco >= umbral_disco:
        problemas["high_disk"] = f"Disco al {disco:.1f}% (umbral: {umbral_disco:.1f}%)."

    return problemas


def ejecutar_monitor() -> None:
    intervalo = max(10, int(os.getenv("MONITOR_INTERVAL_SECONDS", "60")))
    cooldown = max(60, int(os.getenv("ALERT_COOLDOWN_SECONDS", "1800")))
    alertas_activas: dict[str, float] = {}

    logger.info("Monitor VITALIA iniciado; intervalo=%ss", intervalo)
    while True:
        ahora = time.monotonic()
        problemas = obtener_problemas()

        for clave, detalle in problemas.items():
            ultima_alerta = alertas_activas.get(clave)
            if ultima_alerta is None or ahora - ultima_alerta >= cooldown:
                if enviar_correo(f"[VITALIA] Alerta: {clave}", detalle):
                    alertas_activas[clave] = ahora

        for clave in list(alertas_activas):
            if clave not in problemas:
                enviar_correo(
                    f"[VITALIA] Recuperación: {clave}",
                    f"La condición de alerta '{clave}' ya no se detecta.",
                )
                del alertas_activas[clave]

        time.sleep(intervalo)


if __name__ == "__main__":
    ejecutar_monitor()