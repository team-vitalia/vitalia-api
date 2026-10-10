"""
Router de WebSockets para notificaciones en tiempo real de VITALIA (Caso de Uso CU-11).

Ofrece:
1. Endpoint WebSocket (`/ws/notifications/{client_id}`): Permite a la app React Native conectarse y mantener canal bidireccional.
2. Endpoints HTTP de prueba (`POST /ws/send-test/{client_id}` y `POST /ws/broadcast-test`): Para disparar notificaciones desde FastAPI y probar la recepción en la app.
"""

import datetime
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from app.services.connection_manager import manager

logger = logging.getLogger("vitalia.websocket_router")

router = APIRouter(
    prefix="/ws",
    tags=["WebSockets & Notificaciones"]
)


@router.websocket("/notifications/{client_id}")
async def websocket_notifications_endpoint(websocket: WebSocket, client_id: str):
    """
    Endpoint WebSocket principal para notificaciones.
    
    Parámetros:
    - client_id: Identificador único del cliente o usuario (ej. 'doctor_1', 'paciente_10').
    
    Flujo de ejecución:
    1. Acepta la conexión e informa al cliente con un mensaje de bienvenida.
    2. Mantiene un bucle continuo escuchando pings o mensajes del cliente.
    3. Responde automáticamente a eventos 'ping' con un 'pong' con timestamp.
    4. Atrapa WebSocketDisconnect y excepciones para limpiar recursos limpiamente.
    """
    # 1. Aceptar y registrar la conexión en ConnectionManager
    await manager.connect(client_id, websocket)

    # 2. Enviar mensaje inicial de confirmación de conexión
    await manager.send_personal_message(
        {
            "type": "connection_established",
            "client_id": client_id,
            "message": f"Conexión establecida con éxito en el servidor VITALIA para client_id='{client_id}'",
            "timestamp": datetime.datetime.now().isoformat()
        },
        client_id
    )

    try:
        # Bucle principal de lectura de mensajes enviados desde el frontend
        while True:
            # Intentar recibir primero como estructura JSON
            try:
                data = await websocket.receive_json()
                logger.info(f"JSON desde client_id='{client_id}': {data}")

                # Responder a la prueba de ping/pong bidireccional
                if isinstance(data, dict) and data.get("type") == "ping":
                    await manager.send_personal_message(
                        {
                            "type": "pong",
                            "message": "Pong recibido desde el servidor FastAPI",
                            "client_id": client_id,
                            "received_at": datetime.datetime.now().isoformat()
                        },
                        client_id
                    )
                else:
                    # Respuesta Eco genérica para otros payloads JSON
                    await manager.send_personal_message(
                        {
                            "type": "echo",
                            "message": "Servidor VITALIA procesó tu mensaje",
                            "original_payload": data,
                            "timestamp": datetime.datetime.now().isoformat()
                        },
                        client_id
                    )

            except Exception:
                # Si no es un JSON válido, leer como texto plano
                text_data = await websocket.receive_text()
                logger.info(f"Texto plano desde client_id='{client_id}': {text_data}")

                if text_data.strip().lower() == "ping":
                    await manager.send_personal_message(
                        {
                            "type": "pong",
                            "message": "Pong recibido desde el servidor FastAPI (Texto)",
                            "timestamp": datetime.datetime.now().isoformat()
                        },
                        client_id
                    )
                else:
                    await manager.send_personal_message(
                        f"Eco del servidor VITALIA: {text_data}",
                        client_id
                    )

    except WebSocketDisconnect:
        # Desconexión normal iniciada por el cliente o por pérdida de red
        logger.info(f"Cliente desconectado limpiamente: client_id='{client_id}'")
        manager.disconnect(client_id)
    except Exception as e:
        # Captura de cualquier error o cierre abrupto de la conexión
        logger.error(f"Error o desconexión abrupta en client_id='{client_id}': {e}")
        manager.disconnect(client_id)


# --- ENDPOINTS REST AUXILIARES DE PRUEBA ---

@router.post("/send-test/{client_id}")
async def send_test_notification(client_id: str, payload: Optional[Dict[str, Any]] = None):
    """
    Endpoint HTTP REST para enviar una notificación de prueba a un cliente específico conectado.
    """
    mensaje = payload or {
        "type": "notification",
        "title": "Notificación Personalizada VITALIA",
        "body": f"Hola {client_id}, tienes una nueva notificación en tiempo real.",
        "timestamp": datetime.datetime.now().isoformat()
    }

    exito = await manager.send_personal_message(mensaje, client_id)
    if not exito:
        raise HTTPException(
            status_code=404,
            detail=f"El cliente '{client_id}' no se encuentra conectado actualmente al servidor WebSocket."
        )

    return {
        "status": "enviado",
        "client_id": client_id,
        "mensaje": mensaje
    }


@router.post("/broadcast-test")
async def broadcast_test_notification(payload: Optional[Dict[str, Any]] = None):
    """
    Endpoint HTTP REST para emitir una notificación broadcast a TODOS los clientes conectados.
    """
    mensaje = payload or {
        "type": "broadcast_notification",
        "title": "Aviso General VITALIA",
        "body": "Notificación masiva enviada a todos los usuarios conectados en tiempo real.",
        "timestamp": datetime.datetime.now().isoformat()
    }

    await manager.broadcast(mensaje)
    return {
        "status": "broadcast_exitoso",
        "clientes_conectados": len(manager.active_connections),
        "mensaje": mensaje
    }
