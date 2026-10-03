from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db


client = TestClient(app)


def crear_usuario_prueba(
    id_usuario,
    nombre,
    rol_id
):
    return SimpleNamespace(
        id_PK=id_usuario,
        nombre=nombre,
        correo_electronico=f"{nombre.lower()}@vitalia.com",
        rol_id_FK=rol_id,
        estado="activo"
    )


def test_obtener_citas_sin_token():
    """
    Comprueba que no se puedan consultar citas
    sin autenticación.
    """

    response = client.get(
        "/api/citas/"
    )

    assert response.status_code == 401


def test_doctor_no_puede_consultar_citas():
    """
    Comprueba que un doctor no pueda gestionar citas.
    """

    doctor = crear_usuario_prueba(
        id_usuario=2,
        nombre="Doctor",
        rol_id=2
    )

    def obtener_doctor():
        return doctor

    app.dependency_overrides[get_current_user] = obtener_doctor

    try:
        response = client.get(
            "/api/citas/"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Solo el administrador o recepcionista "
            "pueden gestionar citas"
        )

    finally:
        app.dependency_overrides.clear()


def test_administrador_consulta_citas():
    """
    Comprueba que el administrador pueda consultar citas.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    cita = SimpleNamespace(
        id_PK=1,
        paciente_id_FK=1,
        doctor_id_FK=1,
        fecha="2026-10-10",
        hora_inicio="10:00:00",
        hora_fin="10:30:00",
        estado="programada",
        motivo="Consulta general",
        notas="Primera consulta",
        creado_por=1
    )

    db_falsa = MagicMock()

    db_falsa.query.return_value \
        .order_by.return_value \
        .all.return_value = [cita]

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/citas/"
        )

        assert response.status_code == 200

        datos = response.json()

        assert len(datos) == 1
        assert datos[0]["id_PK"] == 1
        assert datos[0]["paciente_id_FK"] == 1
        assert datos[0]["doctor_id_FK"] == 1
        assert datos[0]["estado"] == "programada"
        assert datos[0]["motivo"] == "Consulta general"
        assert datos[0]["notas"] == "Primera consulta"
        assert datos[0]["creado_por"] == 1

    finally:
        app.dependency_overrides.clear()


def crear_db_para_cita(
    paciente=None,
    doctor=None,
    cita_id=1
):
    db = MagicMock()

    def query_falsa(modelo):
        query = MagicMock()

        def filter_falsa(*args, **kwargs):
            filtro = MagicMock()

            if modelo.__name__ == "Paciente":
                filtro.first.return_value = paciente

            elif modelo.__name__ == "Doctor":
                filtro.first.return_value = doctor

            else:
                filtro.first.return_value = None

            return filtro

        query.filter.side_effect = filter_falsa

        return query

    db.query.side_effect = query_falsa

    def refresh_falsa(objeto):
        # Simula el ID que normalmente asignaría MySQL
        objeto.id_PK = cita_id

    db.refresh.side_effect = refresh_falsa

    return db


def test_crear_cita_correctamente():
    """
    Comprueba que se pueda crear correctamente una cita.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    paciente = SimpleNamespace(
        id_PK=1,
        nombre="Maria"
    )

    doctor = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=2
    )

    db_falsa = crear_db_para_cita(
        paciente=paciente,
        doctor=doctor
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/citas/",
            json={
                "paciente_id_FK": 1,
                "doctor_id_FK": 1,
                "fecha": "2026-10-10",
                "hora_inicio": "10:00:00",
                "hora_fin": "10:30:00",
                "estado": "programada",
                "motivo": "Consulta general",
                "notas": "Primera consulta"
            }
        )

        assert response.status_code == 201

        datos = response.json()

        assert datos["paciente_id_FK"] == 1
        assert datos["doctor_id_FK"] == 1
        assert datos["fecha"] == "2026-10-10"
        assert datos["hora_inicio"] == "10:00:00"
        assert datos["hora_fin"] == "10:30:00"
        assert datos["estado"] == "programada"
        assert datos["motivo"] == "Consulta general"
        assert datos["notas"] == "Primera consulta"
        assert datos["creado_por"] == 1

        assert db_falsa.add.call_count == 1

        cita_creada = db_falsa.add.call_args.args[0]

        assert cita_creada.paciente_id_FK == 1
        assert cita_creada.doctor_id_FK == 1
        assert cita_creada.creado_por == 1

    finally:
        app.dependency_overrides.clear()


def test_crear_cita_paciente_inexistente():
    """
    Comprueba que no se pueda crear una cita
    si el paciente no existe.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    doctor = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=2
    )

    db_falsa = crear_db_para_cita(
        paciente=None,
        doctor=doctor
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/citas/",
            json={
                "paciente_id_FK": 999,
                "doctor_id_FK": 1,
                "fecha": "2026-10-10",
                "hora_inicio": "10:00:00",
                "hora_fin": "10:30:00",
                "estado": "programada"
            }
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "El paciente no existe"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_cita_doctor_inexistente():
    """
    Comprueba que no se pueda crear una cita
    si el doctor no existe.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    paciente = SimpleNamespace(
        id_PK=1,
        nombre="Maria"
    )

    db_falsa = crear_db_para_cita(
        paciente=paciente,
        doctor=None
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/citas/",
            json={
                "paciente_id_FK": 1,
                "doctor_id_FK": 999,
                "fecha": "2026-10-10",
                "hora_inicio": "10:00:00",
                "hora_fin": "10:30:00",
                "estado": "programada"
            }
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "El doctor no existe"
        )

    finally:
        app.dependency_overrides.clear()


def test_recepcionista_puede_crear_cita():
    """
    Comprueba que un recepcionista pueda registrar citas.
    """

    recepcionista = crear_usuario_prueba(
        id_usuario=4,
        nombre="Recepcionista",
        rol_id=4
    )

    paciente = SimpleNamespace(
        id_PK=1,
        nombre="Paciente"
    )

    doctor = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=2
    )

    db_falsa = crear_db_para_cita(
        paciente=paciente,
        doctor=doctor
    )

    def obtener_recepcionista():
        return recepcionista

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = (
        obtener_recepcionista
    )
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/citas/",
            json={
                "paciente_id_FK": 1,
                "doctor_id_FK": 1,
                "fecha": "2026-10-15",
                "hora_inicio": "12:00:00",
                "hora_fin": "12:30:00",
                "estado": "programada",
                "motivo": "Revision"
            }
        )

        assert response.status_code == 201

        datos = response.json()

        assert datos["paciente_id_FK"] == 1
        assert datos["doctor_id_FK"] == 1
        assert datos["creado_por"] == 4

    finally:
        app.dependency_overrides.clear()


def test_crear_cita_sin_motivo_ni_notas():
    """
    Comprueba que una cita pueda crearse
    sin motivo ni notas.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    paciente = SimpleNamespace(
        id_PK=1,
        nombre="Paciente"
    )

    doctor = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=2
    )

    db_falsa = crear_db_para_cita(
        paciente=paciente,
        doctor=doctor
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/citas/",
            json={
                "paciente_id_FK": 1,
                "doctor_id_FK": 1,
                "fecha": "2026-10-20",
                "hora_inicio": "09:00:00",
                "hora_fin": "09:30:00"
            }
        )

        assert response.status_code == 201

        datos = response.json()

        assert datos["paciente_id_FK"] == 1
        assert datos["doctor_id_FK"] == 1
        assert datos["estado"] == "programada"
        assert datos["motivo"] is None
        assert datos["notas"] is None
        assert datos["creado_por"] == 1

    finally:
        app.dependency_overrides.clear()