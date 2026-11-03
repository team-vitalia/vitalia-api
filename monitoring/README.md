# Alertas operativas de VITALIA

El monitor corre como un proceso independiente de FastAPI. Comprueba `/health`, CPU, memoria y espacio en disco; envía un correo al detectar una condición, reenvía como máximo según el periodo de enfriamiento y avisa cuando se recupera.

## Instalación en una VPS Linux

1. Copia el repositorio a `/opt/vitalia-api` y confirma que FastAPI esté accesible desde la VPS.
2. Confirma que Python 3 esté instalado:

   ```bash
   python3 --version
   ```

3. Crea el archivo privado de configuración, edita los valores SMTP, destinatario y umbrales, y limita sus permisos:

   ```bash
   sudo cp /opt/vitalia-api/monitoring/vitalia-monitor.env.example /etc/vitalia-monitor.env
   sudo chmod 600 /etc/vitalia-monitor.env
   sudo nano /etc/vitalia-monitor.env
   ```

   Para Gmail, usa una contraseña de aplicación. No guardes las credenciales reales en el repositorio.

4. Crea el usuario de servicio y permite que lea el monitor y su entorno virtual:

   ```bash
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin vitalia-monitor
   sudo chown -R vitalia-monitor:vitalia-monitor /opt/vitalia-api/monitoring
   ```

5. Instala e inicia el servicio:

   ```bash
   sudo cp /opt/vitalia-api/monitoring/vitalia-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now vitalia-monitor
   sudo systemctl status vitalia-monitor
   sudo journalctl -u vitalia-monitor -f
   ```

`/health` detecta que la API no responde, pero no comprueba la base de datos. Para alertas de conectividad con MySQL, configura `MONITOR_API_URL` con `/health/database` o amplía el health check de la aplicación.

Este monitor funciona mientras la VPS siga encendida. Para recibir aviso si la VPS completa pierde red o se apaga, configura adicionalmente un monitor externo (por ejemplo, UptimeRobot) apuntando a la URL pública de `/health`.