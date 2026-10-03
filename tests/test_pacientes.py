from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_obtener_pacientes_sin_token():
    response = client.get(
        "/api/pacientes/"
    )

    assert response.status_code == 401


def test_crear_paciente_sin_token():
    response = client.post(
        "/api/pacientes/",
        json={
            "nombre": "Juan",
            "apellido": "Pérez",
            "fecha_nacimiento": "2000-01-15",
            "genero": "Masculino",
            "telefono": "5512345678",
            "direccion": "Ciudad de México",
            "correo_electronico": "juan@example.com"
        }
    )

    assert response.status_code == 401