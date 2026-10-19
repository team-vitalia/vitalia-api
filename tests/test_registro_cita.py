import pytest
from fastapi.testclient import TestClient
from app.main import app
from datetime import date, time

client = TestClient(app)

def obtener_token_recepcion():
    """Simula el login de un recepcionista."""
    response = client.post("/api/auth/login", json={
        "correo_electronico": "recepcion@gmail.com",  # Cambia por un usuario de recepción real
        "password": "12345678"
    })
    assert response.status_code == 200, "El login de recepción falló"
    return response.json()["access_token"]

def obtener_token_doctor():
    """Simula el login de un doctor."""
    response = client.post("/api/auth/login", json={
        "correo_electronico": "doctor@gmail.com",
        "password": "12345678"
    })
    assert response.status_code == 200, "El login del doctor falló"
    return response.json()["access_token"]


def test_crear_cita_exitosa():
    """Prueba que recepción puede crear una cita correctamente."""
    token = obtener_token_recepcion()
    headers = {"Authorization": f"Bearer {token}"}

    # Datos de prueba (ajusta los IDs según tu base de datos)
    payload = {
        "paciente_id_FK": 1,
        "doctor_id_FK": 2,
        "fecha": str(date.today()),
        "hora_inicio": "10:00:00",
        "hora_fin": "11:00:00",
        "estado": "programada",
        "motivo": "Consulta de prueba automatizada",
        "notas": "Notas generadas por test"
    }

    response = client.post("/api/citas/", json=payload, headers=headers)
    
    assert response.status_code == 201, f"Error al crear cita: {response.text}"
    data = response.json()
    assert data["paciente_id_FK"] == payload["paciente_id_FK"]
    assert data["doctor_id_FK"] == payload["doctor_id_FK"]
    assert data["motivo"] == payload["motivo"]


def test_registrar_llegada_paciente():
    """Prueba que recepción puede registrar la llegada de un paciente a la cola."""
    token = obtener_token_recepcion()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Obtener las colas ya existentes hoy
    response_colas = client.get("/api/colas/", headers=headers)
    assert response_colas.status_code == 200
    colas_hoy = response_colas.json()
    citas_con_cola = {c["cita_id_FK"] for c in colas_hoy}

    # 2. Obtener todas las citas
    response_citas = client.get("/api/citas/", headers=headers)
    assert response_citas.status_code == 200
    citas = response_citas.json()

    if not citas:
        pytest.skip("No hay citas disponibles en la base de datos")

    # 3. Filtrar solo las citas que NO tienen cola registrada hoy
    citas_disponibles = [c for c in citas if c["id_PK"] not in citas_con_cola]

    if not citas_disponibles:
        pytest.skip("Todas las citas de hoy ya tienen un turno registrado. Crea una cita nueva para probar esto.")

    cita_id = citas_disponibles[0]["id_PK"]

    # 4. Registrar la llegada
    payload = {
        "cita_id_FK": cita_id,
        "prioridad": "normal"
    }

    response = client.post("/api/colas/", json=payload, headers=headers)
    
    assert response.status_code == 201, f"Error al registrar llegada: {response.text}"
    data = response.json()
    assert data["cita_id_FK"] == cita_id
    assert data["estado"] == "en_espera"
    assert data["numero_cola"] is not None

def test_cambiar_estado_cita_a_completada():
    """Prueba que un doctor puede marcar su cita como completada."""
    token = obtener_token_doctor()
    headers = {"Authorization": f"Bearer {token}"}

    # Obtener las citas del doctor
    response_citas = client.get("/api/citas/mis-consultas", headers=headers)
    assert response_citas.status_code == 200
    citas = response_citas.json()

    if not citas:
        pytest.skip("El doctor no tiene citas para completar")

    cita_id = citas[0]["id_PK"]

    response = client.put(
        f"/api/citas/{cita_id}/estado?nuevo_estado=completada",
        headers=headers
    )

    assert response.status_code == 200, f"Error al completar cita: {response.text}"
    data = response.json()
    assert data["cita"]["estado"] == "completada"
    # Verificar que se agregó la nota automática
    assert "Cita terminada el" in data["cita"]["notas"], "No se agregó la nota de cita terminada"


def test_listar_colas_del_dia():
    """Prueba que se pueden listar las colas activas del día."""
    token = obtener_token_recepcion()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/colas/", headers=headers)
    
    assert response.status_code == 200
    assert isinstance(response.json(), list), "La respuesta debe ser una lista"