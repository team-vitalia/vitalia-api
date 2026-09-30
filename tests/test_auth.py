from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_login_correo_invalido():
    response = client.post(
        "/api/auth/login",
        json={
            "correo_electronico": "correo_que_no_existe@vitalia.com",
            "password": "password123"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


def test_login_sin_datos():
    response = client.post(
        "/api/auth/login",
        json={}
    )

    assert response.status_code == 422
    
def test_usuario_actual_sin_token():
    response = client.get(
        "/api/auth/me"
    )

    assert response.status_code == 401