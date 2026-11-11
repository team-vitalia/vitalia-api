from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_pr007_envio_correo():
    payload = {
        "destinatario": "al222310412@gmail.com",
        "asunto": "Notificacion VITALIA - Prueba PR-007",
        "mensaje": "Mensaje de prueba de envio de correo electronico en VITALIA."
    }
    respuesta = client.post("/email-prueba", json=payload)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos.get("ok") is True
    assert datos.get("destinatario") == "al222310412@gmail.com"
