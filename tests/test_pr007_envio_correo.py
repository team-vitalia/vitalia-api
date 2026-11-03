import requests

def test_pr020_envio_correo():
    url = "http://127.0.0.1:8000/email-prueba"
    payload = {
        "destinatario": "al222310412@gmail.com",
        "asunto": "Notificacion VITALIA - Prueba PR-007",
        "mensaje": "Mensaje de prueba de envio de correo electronico en VITALIA."
    }
    respuesta = requests.post(url, json=payload)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos.get("ok") is True
    assert datos.get("destinatario") == "al222310412@gmail.com"
