from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db


client = TestClient(app)

# Primera funcion
def test_obtener_usuarios_sin_token():
    response = client.get(
        "/api/usuarios/"
    )

    assert response.status_code == 401


def crear_usuario_prueba(
    id_usuario,
    nombre,
    correo,
    rol_id,
    rol_nombre,
    estado="activo"
):
    return SimpleNamespace(
        id_PK=id_usuario,
        nombre=nombre,
        correo_electronico=correo,
        rol_id_FK=rol_id,
        rol=SimpleNamespace(
            nombre=rol_nombre
        ),
        estado=estado,
        creado_en=None,
        ultimo_acceso=None
    )


def crear_db_falsa(usuarios):
    db = MagicMock()

    db.query.return_value.order_by.return_value.all.return_value = usuarios

    return db

# Segunda funcion
def test_administrador_consulta_usuarios():
    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        correo="admin@vitalia.com",
        rol_id=1,
        rol_nombre="Administrador"
    )

    usuarios = [
        administrador,
        crear_usuario_prueba(
            id_usuario=2,
            nombre="Juan Perez",
            correo="juan@vitalia.com",
            rol_id=2,
            rol_nombre="Doctor"
        )
    ]

    db_falsa = crear_db_falsa(usuarios)

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/usuarios/"
        )

        assert response.status_code == 200

    finally:
        app.dependency_overrides.clear()

# Tercera funcion
def test_usuario_normal_consulta_usuarios():
    usuario_normal = crear_usuario_prueba(
        id_usuario=2,
        nombre="Juan Perez",
        correo="juan@vitalia.com",
        rol_id=2,
        rol_nombre="Doctor"
    )

    def obtener_usuario_normal():
        return usuario_normal

    app.dependency_overrides[get_current_user] = obtener_usuario_normal

    try:
        response = client.get(
            "/api/usuarios/"
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Solo el administrador puede consultar los usuarios"
        )

    finally:
        app.dependency_overrides.clear()


# Quarta funcion
def test_respuesta_contiene_usuarios():
    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        correo="admin@vitalia.com",
        rol_id=1,
        rol_nombre="Administrador"
    )

    usuarios = [
        administrador,
        crear_usuario_prueba(
            id_usuario=2,
            nombre="Juan Perez",
            correo="juan@vitalia.com",
            rol_id=2,
            rol_nombre="Doctor"
        ),
        crear_usuario_prueba(
            id_usuario=3,
            nombre="Maria Lopez",
            correo="maria@vitalia.com",
            rol_id=3,
            rol_nombre="Paciente"
        )
    ]

    db_falsa = crear_db_falsa(usuarios)

    def obtener_admin():
        return administrador

    def obtener_db():
        return db_falsa

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/usuarios/"
        )

        assert response.status_code == 200

        datos = response.json()

        assert len(datos) == 3

        assert datos[0]["nombre"] == "Administrador"
        assert datos[0]["correo_electronico"] == "admin@vitalia.com"
        assert datos[0]["rol"] == "Administrador"

        assert datos[1]["nombre"] == "Juan Perez"
        assert datos[1]["correo_electronico"] == "juan@vitalia.com"
        assert datos[1]["rol"] == "Doctor"

        assert datos[2]["nombre"] == "Maria Lopez"
        assert datos[2]["correo_electronico"] == "maria@vitalia.com"
        assert datos[2]["rol"] == "Paciente"

    finally:
        app.dependency_overrides.clear()
