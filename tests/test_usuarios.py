from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db


# Crea un cliente para realizar peticiones de prueba a nuestra API
client = TestClient(app)


# Primera función
# Sirve para comprobar que un usuario no pueda consultar
# la lista de usuarios si no está autenticado.
def test_obtener_usuarios_sin_token():
    response = client.get(
        "/api/usuarios/"
    )

    # Verifica que la API rechace la petición con 401
    # porque no se proporcionó un token de autenticación.
    assert response.status_code == 401


# Función auxiliar para crear usuarios de prueba.
# Permite crear usuarios falsos sin tener que utilizar
# usuarios reales de la base de datos.
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


# Función auxiliar para crear una base de datos falsa.
# MagicMock permite simular las operaciones que normalmente
# realizaría la base de datos.
def crear_db_falsa(usuarios):
    db = MagicMock()

    # Simula una consulta que obtiene todos los usuarios
    # ordenados desde la base de datos.
    db.query.return_value.order_by.return_value.all.return_value = usuarios

    return db


# Segunda función
# Sirve para comprobar que un administrador pueda
# consultar la lista de usuarios.
def test_administrador_consulta_usuarios():

    # Creamos un administrador falso para la prueba.
    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        correo="admin@vitalia.com",
        rol_id=1,
        rol_nombre="Administrador"
    )

    # Creamos una lista de usuarios falsos.
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

    # Creamos una base de datos falsa que devolverá
    # los usuarios anteriores.
    db_falsa = crear_db_falsa(usuarios)

    # Simula que el usuario autenticado es el administrador.
    def obtener_admin():
        return administrador

    # Simula la conexión a la base de datos.
    def obtener_db():
        return db_falsa

    # Reemplazamos temporalmente las dependencias reales
    # por nuestras funciones falsas.
    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/usuarios/"
        )

        # Verifica que el administrador pueda consultar
        # correctamente la lista de usuarios.
        assert response.status_code == 200

    finally:
        # Elimina las dependencias falsas para que no afecten
        # a las demás pruebas.
        app.dependency_overrides.clear()


# Tercera función
# Sirve para comprobar que un usuario que NO es administrador
# no pueda consultar la lista de usuarios.
def test_usuario_normal_consulta_usuarios():

    # Creamos un usuario normal con rol de Doctor.
    usuario_normal = crear_usuario_prueba(
        id_usuario=2,
        nombre="Juan Perez",
        correo="juan@vitalia.com",
        rol_id=2,
        rol_nombre="Doctor"
    )

    # Simula que el usuario autenticado es el Doctor.
    def obtener_usuario_normal():
        return usuario_normal

    # Reemplazamos temporalmente la dependencia del usuario
    # autenticado por nuestro usuario de prueba.
    app.dependency_overrides[get_current_user] = obtener_usuario_normal

    try:
        response = client.get(
            "/api/usuarios/"
        )

        # Verifica que el sistema rechace el acceso
        # porque solamente el administrador puede consultar usuarios.
        assert response.status_code == 403

        # Verifica que se muestre el mensaje esperado.
        assert response.json()["detail"] == (
            "Solo el administrador puede consultar los usuarios"
        )

    finally:
        # Elimina las dependencias falsas al terminar la prueba.
        app.dependency_overrides.clear()


# Cuarta función
# Sirve para comprobar que la respuesta de la API
# contenga correctamente los usuarios y sus datos.
def test_respuesta_contiene_usuarios():

    # Creamos un administrador falso.
    administrador = crear_usuario_prueba(
        id_usuario=1,
        nombre="Administrador",
        correo="admin@vitalia.com",
        rol_id=1,
        rol_nombre="Administrador"
    )

    # Creamos tres usuarios falsos con diferentes roles.
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

    # Creamos una base de datos falsa que devolverá
    # los tres usuarios.
    db_falsa = crear_db_falsa(usuarios)

    # Simula que el usuario autenticado es el administrador.
    def obtener_admin():
        return administrador

    # Simula la conexión a la base de datos.
    def obtener_db():
        return db_falsa

    # Reemplazamos temporalmente las dependencias reales
    # por las dependencias falsas.
    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    try:
        response = client.get(
            "/api/usuarios/"
        )

        # Verifica que la petición sea exitosa.
        assert response.status_code == 200

        # Convierte la respuesta JSON en datos de Python.
        datos = response.json()

        # Verifica que la API haya devuelto exactamente
        # tres usuarios.
        assert len(datos) == 3

        # Verifica los datos del primer usuario.
        assert datos[0]["nombre"] == "Administrador"
        assert datos[0]["correo_electronico"] == "admin@vitalia.com"
        assert datos[0]["rol"] == "Administrador"

        # Verifica los datos del segundo usuario.
        assert datos[1]["nombre"] == "Juan Perez"
        assert datos[1]["correo_electronico"] == "juan@vitalia.com"
        assert datos[1]["rol"] == "Doctor"

        # Verifica los datos del tercer usuario.
        assert datos[2]["nombre"] == "Maria Lopez"
        assert datos[2]["correo_electronico"] == "maria@vitalia.com"
        assert datos[2]["rol"] == "Paciente"

    finally:
        # Elimina las dependencias falsas para no afectar
        # otras pruebas.
        app.dependency_overrides.clear()