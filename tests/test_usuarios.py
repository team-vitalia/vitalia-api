from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_obtener_usuarios_sin_token():
    response = client.get(
        "/api/usuarios/"
    )

    assert response.status_code == 401