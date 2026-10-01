from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


# Crea un cliente para realizar peticiones de prueba a nuestra API
client = TestClient(app)


# Primera función
# Sirve para comprobar que el sistema rechace el login
# cuando se proporciona un correo electrónico que no existe.
def test_login_correo_invalido():
    response = client.post(
        "/api/auth/login",
        json={
            "correo_electronico": "correo_que_no_existe@vitalia.com",
            "password": "password123"
        }
    )

    # Verifica que la API responda con error 401 (No autorizado)
    assert response.status_code == 401

    # Verifica que se muestre el mensaje de error esperado
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


# Segunda función
# Sirve para comprobar que el sistema no permita iniciar sesión
# cuando no se envían los datos necesarios.
def test_login_sin_datos():
    response = client.post(
        "/api/auth/login",
        json={}
    )

    # Verifica que FastAPI responda con 422
    # porque faltan los campos obligatorios.
    assert response.status_code == 422


# Tercera función
# Sirve para comprobar que un usuario no pueda consultar
# sus datos sin proporcionar un token de autenticación.
def test_usuario_actual_sin_token():
    response = client.get(
        "/api/auth/me"
    )

    # Verifica que la API rechace la petición con 401
    # porque no se proporcionó un token.
    assert response.status_code == 401


# Cuarta función
# Sirve para comprobar que el login funcione correctamente
# cuando la autenticación es exitosa.
def test_login_correcto():

    # Creamos un resultado falso para simular
    # que la autenticación fue exitosa.
    resultado_falso = {
        "usuario": None,
        "access_token": "token-de-prueba"
    }

    # Reemplazamos temporalmente la función autenticar_usuario
    # para no depender de la autenticación real durante esta prueba.
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

    # Verifica que el login haya sido exitoso.
    assert response.status_code == 200

    # Obtiene los datos que devolvió la API.
    datos = response.json()

    # Verifica que se haya recibido correctamente el token.
    assert datos["access_token"] == "token-de-prueba"

    # Verifica que el tipo de token sea Bearer.
    assert datos["token_type"] == "bearer"


# Quinta función
# Sirve para comprobar que el sistema rechace el login
# cuando la contraseña proporcionada es incorrecta.
def test_login_contrasena_incorrecta():

    # Simulamos que la autenticación falló.
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

    # Verifica que la API responda con 401 (No autorizado).
    assert response.status_code == 401

    # Verifica que se muestre el mensaje de error esperado.
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


# Sexta función
# Sirve para comprobar que un usuario que no puede autenticarse
# sea rechazado y no pueda iniciar sesión.
def test_login_usuario_inactivo():

    # Simulamos que la autenticación no fue exitosa.
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

    # Verifica que la API rechace el inicio de sesión.
    assert response.status_code == 401

    # Verifica que se muestre el mensaje de error esperado.
    assert response.json()["detail"] == "Correo o contraseña incorrectos"