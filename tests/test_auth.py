from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

# Primera funcion
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

# Segunda funcion
def test_login_sin_datos():
    response = client.post(
        "/api/auth/login",
        json={}
    )

    assert response.status_code == 422

# Tercera funcion
def test_usuario_actual_sin_token():
    response = client.get(
        "/api/auth/me"
    )

    assert response.status_code == 401

# Quarta funcion
def test_login_correcto():
    resultado_falso = {
        "usuario": None,
        "access_token": "token-de-prueba"
    }

    with patch(
        "app.routers.auth.autenticar_usuario",
        return_value=resultado_falso
    ):
        response = client.post(
            "/api/auth/login",
            json={
                "correo_electronico": "admin@vitalia.com",
                "password": "password123"
            }
        )

    assert response.status_code == 200

    datos = response.json()

    assert datos["access_token"] == "token-de-prueba"
    assert datos["token_type"] == "bearer"

# Quinta funcion
def test_login_contrasena_incorrecta():
    with patch(
        "app.routers.auth.autenticar_usuario",
        return_value=None
    ):
        response = client.post(
            "/api/auth/login",
            json={
                "correo_electronico": "admin@vitalia.com",
                "password": "contrasena_incorrecta"
            }
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"

# Sexta funcion
def test_login_usuario_inactivo():
    with patch(
        "app.routers.auth.autenticar_usuario",
        return_value=None
    ):
        response = client.post(
            "/api/auth/login",
            json={
                "correo_electronico": "usuario@vitalia.com",
                "password": "password123"
            }
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"
