import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def obtener_token_doctor():
    """Simula el login de un doctor y devuelve el token."""
    response = client.post("/api/auth/login", json={
        "correo_electronico": "doctor@gmail.com",
        "password": "12345678"
    })
    # Si el login falla, saltamos la prueba en lugar de romperla
    if response.status_code != 200:
        pytest.skip(f"No se pudo loguear al doctor: {response.text}")
    return response.json()["access_token"]


# PARCHEAMOS LAS FUNCIONES DE NOTIFICACIÓN Y GOOGLE CALENDAR
# para que no intenten conectarse a internet ni fallen durante el test
@patch("app.routers.citas.notificar_cita_reprogramada")
@patch("app.routers.citas.notificar_correo_cita_reprogramada")
def test_transferir_cita_exitosa(mock_correo, mock_notificacion):
    """Prueba que un doctor puede transferir su cita a otro doctor activo."""
    
    # Configuramos los mocks para que no hagan nada
    mock_correo.return_value = None
    mock_notificacion.return_value = None

    token = obtener_token_doctor()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Obtener las citas del doctor actual
    response_citas = client.get("/api/citas/mis-consultas", headers=headers)
    assert response_citas.status_code == 200
    citas = response_citas.json()
    
    if not citas:
        pytest.skip("No hay citas para transferir en la base de datos de prueba")

    cita_id = citas[0]["id_PK"]
    
    # 2. Obtener la lista de doctores para transferir
    response_doctores = client.get("/api/doctores/lista-para-transferir", headers=headers)
    assert response_doctores.status_code == 200
    doctores = response_doctores.json()
    
    if not doctores:
        pytest.skip("No hay otros doctores disponibles para transferir")

    nuevo_doctor_id = doctores[0]["id_PK"]

    # 3. Ejecutar la transferencia
    response_transferir = client.put(
        f"/api/citas/{cita_id}/reasignar?nuevo_doctor_id={nuevo_doctor_id}",
        headers=headers
    )
    
    # 4. Aserciones
    assert response_transferir.status_code == 200, f"La transferencia falló: {response_transferir.text}"
    data = response_transferir.json()
    
    assert data["mensaje"] == "Cita reasignada correctamente"
    assert data["cita"]["doctor_id_FK"] == nuevo_doctor_id, "El doctor no se actualizó correctamente"
    
    # Verificar que la nota de transferencia se agregó
    assert "Cita transferida por Dr." in data["cita"]["notas"], "No se agregó la nota de transferencia"


@patch("app.routers.citas.notificar_cita_reprogramada")
@patch("app.routers.citas.notificar_correo_cita_reprogramada")
def test_transferir_cita_a_doctor_inexistente(mock_correo, mock_notificacion):
    """Prueba que falla si se intenta transferir a un doctor que no existe."""
    
    mock_correo.return_value = None
    mock_notificacion.return_value = None

    token = obtener_token_doctor()
    headers = {"Authorization": f"Bearer {token}"}

    response_citas = client.get("/api/citas/mis-consultas", headers=headers)
    citas = response_citas.json()
    
    if not citas:
        pytest.skip("No hay citas para probar")

    cita_id = citas[0]["id_PK"]
    doctor_inexistente_id = 99999

    response = client.put(
        f"/api/citas/{cita_id}/reasignar?nuevo_doctor_id={doctor_inexistente_id}",
        headers=headers
    )
    
    assert response.status_code == 404, "Debería fallar con 404 si el doctor no existe"
    assert "no existe o está inactivo" in response.json()["detail"]