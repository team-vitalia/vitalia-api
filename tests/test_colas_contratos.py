from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db


client = TestClient(app)


def crear_usuario_prueba(id_usuario, nombre, rol_id):
    return SimpleNamespace(
        id_PK=id_usuario,
        nombre=nombre,
        correo_electronico=f"{nombre.lower()}@vitalia.com",
        rol_id_FK=rol_id,
        estado="activo"
    )


def configurar_dependencias(usuario, db):
    app.dependency_overrides[get_current_user] = lambda: usuario
    app.dependency_overrides[get_db] = lambda: db


def test_doctor_no_puede_registrar_llegada():
    """
    Comprueba que solo recepcion o administrador
    puedan registrar la llegada de un paciente.
    """

    doctor = crear_usuario_prueba(2, "Doctor", 2)

    configurar_dependencias(doctor, MagicMock())

    try:
        response = client.post(
            "/api/colas/",
            json={"cita_id_FK": 1}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Solo recepción o admin pueden registrar llegadas"
        )

    finally:
        app.dependency_overrides.clear()


def test_registrar_llegada_cita_inexistente():
    """
    Comprueba que no se pueda registrar la llegada
    de una cita que no existe.
    """

    recepcionista = crear_usuario_prueba(4, "Recepcionista", 4)

    db_falsa = MagicMock()
    db_falsa.query.return_value \
        .filter.return_value \
        .first.return_value = None

    configurar_dependencias(recepcionista, db_falsa)

    try:
        response = client.post(
            "/api/colas/",
            json={"cita_id_FK": 999}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "La cita no existe"
        assert db_falsa.add.call_count == 0

    finally:
        app.dependency_overrides.clear()


def test_llamar_paciente_actualiza_cola():
    """
    Comprueba que al cambiar una cola a 'llamado'
    se registre la hora de llamado y el consultorio.
    """

    recepcionista = crear_usuario_prueba(4, "Recepcionista", 4)

    cola = SimpleNamespace(
        id_PK=1,
        cita_id_FK=10,
        paciente_id_FK=1,
        doctor_id_FK=1,
        numero_cola="001",
        estado="en_espera",
        hora_registro=datetime.now(),
        prioridad="normal",
        hora_llamado=None,
        numero_consultorio=None
    )

    db_falsa = MagicMock()
    db_falsa.query.return_value \
        .filter.return_value \
        .first.return_value = cola

    configurar_dependencias(recepcionista, db_falsa)

    try:
        response = client.patch(
            "/api/colas/1",
            json={
                "estado": "llamado",
                "numero_consultorio": "3"
            }
        )

        assert response.status_code == 200

        datos = response.json()

        assert datos["estado"] == "llamado"
        assert datos["numero_consultorio"] == "3"
        assert datos["hora_llamado"] is not None
        assert db_falsa.commit.call_count == 1

    finally:
        app.dependency_overrides.clear()


def test_crear_contrato_fecha_fin_anterior_a_inicio():
    """
    Comprueba que no se pueda crear un contrato
    cuya fecha de fin sea anterior a la de inicio.
    """

    administrador = crear_usuario_prueba(1, "Administrador", 1)

    configurar_dependencias(administrador, MagicMock())

    try:
        response = client.post(
            "/api/contratos/",
            json={
                "doctor_id_FK": 1,
                "fecha_inicio": "2026-10-10",
                "fecha_fin": "2026-01-01",
                "estado": "activo",
                "tipo_contrato": "Tiempo completo",
                "salario": 15000
            }
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()