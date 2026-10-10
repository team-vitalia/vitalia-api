import logging
from typing import Dict, Any, Union
from fastapi import WebSocket

logger = logging.getLogger("vitalia.websocket")
logging.basicConfig(level=logging.INFO)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if client_id in self.active_connections:
            old_ws = self.active_connections[client_id]
            try:
                await old_ws.close(code=1000)
            except Exception:
                pass
            del self.active_connections[client_id]

        self.active_connections[client_id] = websocket
        logger.info(
            f"🟢 [WebSocket] Cliente conectado: client_id='{client_id}'. "
            f"Total de conexiones activas: {len(self.active_connections)}"
        )

    def disconnect(self, client_id: str) -> None:
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(
                f"🔴 [WebSocket] Cliente desconectado: client_id='{client_id}'. "
                f"Conexiones activas restantes: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: Union[str, dict], client_id: str) -> bool:
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                if isinstance(message, dict):
                    await websocket.send_json(message)
                else:
                    await websocket.send_text(str(message))
                logger.info(f"📤 [WebSocket] Mensaje privado enviado a client_id='{client_id}': {message}")
                return True
            except Exception as e:
                logger.error(f"⚠️ [WebSocket] Error al enviar mensaje a client_id='{client_id}': {e}")
                self.disconnect(client_id)
                return False
        else:
            logger.warning(f"⚠️ [WebSocket] Intento de envío fallido. Cliente no conectado: client_id='{client_id}'")
            return False

    async def broadcast(self, message: Union[str, dict]) -> None:
        logger.info(f"📢 [WebSocket] Iniciando broadcast a {len(self.active_connections)} clientes activos.")
        disconnected_clients = []

        for client_id, connection in list(self.active_connections.items()):
            try:
                if isinstance(message, dict):
                    await connection.send_json(message)
                else:
                    await connection.send_text(str(message))
            except Exception as e:
                logger.error(f"⚠️ [WebSocket] Error enviando broadcast a client_id='{client_id}': {e}")
                disconnected_clients.append(client_id)

        for client_id in disconnected_clients:
            self.disconnect(client_id)


manager = ConnectionManager()
