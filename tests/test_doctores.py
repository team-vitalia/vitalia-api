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


def test_obtener_doctores_sin_token():
    """
    Comprueba que no se puedan consultar doctores
    sin autenticación.
    """

    response = client.get(
        "/api/doctores/"
    )

    assert response.status_code == 401


def test_doctor_no_puede_consultar_doctores():
    """
    Comprueba que un usuario con rol Doctor
    no pueda gestionar doctores.
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
            "/api/doctores/"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Solo el administrador o recepcionista "
            "pueden gestionar doctores"
        )

    finally:
        app.dependency_overrides.clear()


def test_administrador_consulta_doctores():
    """
    Comprueba que el administrador pueda consultar doctores.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    doctor = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=2,
        estado="activo",
        usuario=SimpleNamespace(
            nombre="Doctor Prueba"
        ),
        especialidad=SimpleNamespace(
            nombre="Cardiologia"
        )
    )

    db_falsa = MagicMock()

    db_falsa.query.return_value \
        .join.return_value \
        .outerjoin.return_value \
        .filter.return_value \
        .all.return_value = [doctor]

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/doctores/"
        )

        assert response.status_code == 200

        datos = response.json()

        assert len(datos) == 1
        assert datos[0]["id_PK"] == 1
        assert datos[0]["nombre"] == "Doctor Prueba"
        assert datos[0]["especialidad"] == "Cardiologia"
        assert datos[0]["estado"] == "activo"

    finally:
        app.dependency_overrides.clear()


def test_recepcionista_consulta_doctores():
    """
    Comprueba que un recepcionista pueda consultar doctores.
    """

    recepcionista = crear_usuario_prueba(
        id_usuario=4,
        nombre="Recepcionista",
        rol_id=4
    )

    db_falsa = MagicMock()

    db_falsa.query.return_value \
        .join.return_value \
        .outerjoin.return_value \
        .filter.return_value \
        .all.return_value = []

    def obtener_recepcionista():
        return recepcionista

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = (
        obtener_recepcionista
    )
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/doctores/"
        )

        assert response.status_code == 200
        assert response.json() == []

    finally:
        app.dependency_overrides.clear()


def crear_db_para_crear_doctor(
    usuario=None,
    doctor_existente=None,
    especialidad=None
):
    db = MagicMock()

    llamadas_query = 0

    def query_falsa(modelo):
        nonlocal llamadas_query

        query = MagicMock()

        def filter_falsa(*args, **kwargs):
            nonlocal llamadas_query

            filtro = MagicMock()

            if modelo.__name__ == "Usuario":
                filtro.first.return_value = usuario

            elif modelo.__name__ == "Doctor":
                filtro.first.return_value = doctor_existente

            elif modelo.__name__ == "Especialidad":
                filtro.first.return_value = especialidad

            else:
                filtro.first.return_value = None

            llamadas_query += 1

            return filtro

        query.filter.side_effect = filter_falsa

        return query

    db.query.side_effect = query_falsa

    db.refresh.side_effect = lambda objeto: None

    return db


def test_crear_doctor_correctamente():
    """
    Comprueba que se pueda crear correctamente
    un registro de doctor.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    usuario = crear_usuario_prueba(
        id_usuario=10,
        nombre="Doctor Nuevo",
        rol_id=2
    )

    especialidad = SimpleNamespace(
        id_PK=1,
        nombre="Medicina General"
    )

    db_falsa = crear_db_para_crear_doctor(
        usuario=usuario,
        doctor_existente=None,
        especialidad=especialidad
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/doctores/",
            json={
                "usuario_id_FK": 10,
                "especialidad_id_FK": 1,
                "numero_licencia": "LIC-TEST-001",
                "estado": "activo",
                "costo_consulta": 500
            }
        )

        assert response.status_code == 201

        datos = response.json()

        assert datos["mensaje"] == (
            "Doctor registrado correctamente"
        )

        doctor = datos["doctor"]

        assert doctor["usuario_id_FK"] == 10
        assert doctor["especialidad_id_FK"] == 1
        assert doctor["numero_licencia"] == "LIC-TEST-001"
        assert doctor["estado"] == "activo"
        assert doctor["costo_consulta"] == 500

        assert db_falsa.add.call_count == 1

    finally:
        app.dependency_overrides.clear()


def test_crear_doctor_usuario_inexistente():
    """
    Comprueba que no se pueda crear un doctor
    si el usuario no existe.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    db_falsa = crear_db_para_crear_doctor(
        usuario=None
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/doctores/",
            json={
                "usuario_id_FK": 999,
                "especialidad_id_FK": 1,
                "numero_licencia": "LIC-999",
                "estado": "activo",
                "costo_consulta": 500
            }
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "El usuario no existe"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_doctor_duplicado():
    """
    Comprueba que un usuario no pueda registrarse
    dos veces como doctor.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    usuario = crear_usuario_prueba(
        id_usuario=10,
        nombre="Doctor",
        rol_id=2
    )

    doctor_existente = SimpleNamespace(
        id_PK=1,
        usuario_id_FK=10
    )

    db_falsa = crear_db_para_crear_doctor(
        usuario=usuario,
        doctor_existente=doctor_existente
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/doctores/",
            json={
                "usuario_id_FK": 10,
                "especialidad_id_FK": 1,
                "numero_licencia": "LIC-001",
                "estado": "activo",
                "costo_consulta": 500
            }
        )

        assert response.status_code == 400

        assert response.json()["detail"] == (
            "Este usuario ya está registrado como doctor"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_doctor_especialidad_inexistente():
    """
    Comprueba que no se pueda crear un doctor
    con una especialidad inexistente.
    """

    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        rol_id=1
    )

    usuario = crear_usuario_prueba(
        id_usuario=10,
        nombre="Doctor",
        rol_id=2
    )

    db_falsa = crear_db_para_crear_doctor(
        usuario=usuario,
        doctor_existente=None,
        especialidad=None
    )

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.post(
            "/api/doctores/",
            json={
                "usuario_id_FK": 10,
                "especialidad_id_FK": 999,
                "numero_licencia": "LIC-999",
                "estado": "activo",
                "costo_consulta": 500
            }
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "La especialidad no existe"
        )

    finally:
        app.dependency_overrides.clear()


def test_recepcionista_puede_crear_doctor():
    """
    Comprueba que un recepcionista también tenga permiso
    para registrar doctores.
    """

    recepcionista = crear_usuario_prueba(
        id_usuario=4,
        nombre="Recepcionista",
        rol_id=4
    )

    usuario = crear_usuario_prueba(
        id_usuario=10,
        nombre="Doctor Nuevo",
        rol_id=2
    )

    db_falsa = crear_db_para_crear_doctor(
        usuario=usuario,
        doctor_existente=None,
        especialidad=None
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
            "/api/doctores/",
            json={
                "usuario_id_FK": 10,
                "especialidad_id_FK": None,
                "numero_licencia": "LIC-RECEP-001",
                "estado": "activo",
                "costo_consulta": 400
            }
        )

        assert response.status_code == 201

        assert response.json()["mensaje"] == (
            "Doctor registrado correctamente"
        )

    finally:
        app.dependency_overrides.clear()