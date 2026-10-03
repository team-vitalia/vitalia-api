from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.role import Role
from app.models.especialidad import Especialidad


client = TestClient(app)


def crear_administrador():
    return SimpleNamespace(
        id_PK=1,
        nombre="Administrador",
        correo_electronico="admin@vitalia.com",
        rol_id_FK=1,
        estado="activo"
    )


def crear_db_para_usuario(
    correo_existente=None,
    rol=None,
    especialidad=None,
    usuario_id=10
):
    db = MagicMock()

    usuario_nuevo = None

    def query_falsa(modelo):
        query = MagicMock()

        def filter_falsa(*args, **kwargs):
            filtro = MagicMock()

            if modelo.__name__ == "Usuario":
                if correo_existente is not None:
                    filtro.first.return_value = correo_existente
                else:
                    filtro.first.return_value = None

            elif modelo is Role:
                filtro.first.return_value = rol

            elif modelo is Especialidad:
                filtro.first.return_value = especialidad

            else:
                filtro.first.return_value = None

            return filtro

        query.filter.side_effect = filter_falsa

        return query

    db.query.side_effect = query_falsa

    def flush_falsa():
        for llamada in db.add.call_args_list:
            objeto = llamada.args[0]

            if objeto.__class__.__name__ == "Usuario":
                objeto.id_PK = usuario_id

    db.flush.side_effect = flush_falsa
    db.refresh.side_effect = lambda objeto: None

    return db


def configurar_administrador(db):
    administrador = crear_administrador()

    def obtener_admin():
        return administrador

    def obtener_db():
        return db

    app.dependency_overrides[get_current_user] = obtener_admin
    app.dependency_overrides[get_db] = obtener_db

    return administrador


def test_crear_usuario_administrador():
    """
    Comprueba que un administrador pueda crear
    un usuario con rol de administrador.
    """

    rol = SimpleNamespace(
        id_PK=1,
        nombre="Administrador",
        esta_activo=True
    )

    db_falsa = crear_db_para_usuario(
        rol=rol,
        usuario_id=20
    )

    configurar_administrador(db_falsa)

    try:
        with patch(
            "app.routers.usuarios.generar_hash_password",
            return_value="hash-falso"
        ):
            response = client.post(
                "/api/usuarios/",
                json={
                    "nombre": "Nuevo Administrador",
                    "correo_electronico": "nuevoadmin@vitalia.com",
                    "password": "password123",
                    "rol_id_FK": 1
                }
            )

        assert response.status_code == 201

        datos = response.json()

        assert datos["id_PK"] == 20
        assert datos["nombre"] == "Nuevo Administrador"
        assert datos["correo_electronico"] == (
            "nuevoadmin@vitalia.com"
        )
        assert datos["rol_id_FK"] == 1
        assert datos["estado"] == "activo"

        assert db_falsa.add.call_count == 1

    finally:
        app.dependency_overrides.clear()


def test_crear_usuario_doctor():
    """
    Comprueba que al crear un usuario con rol Doctor
    también se cree su registro de doctor.
    """

    rol = SimpleNamespace(
        id_PK=2,
        nombre="Doctor",
        esta_activo=True
    )

    especialidad = SimpleNamespace(
        id_PK=1,
        nombre="Medicina General"
    )

    db_falsa = crear_db_para_usuario(
        rol=rol,
        especialidad=especialidad,
        usuario_id=21
    )

    configurar_administrador(db_falsa)

    try:
        with patch(
            "app.routers.usuarios.generar_hash_password",
            return_value="hash-falso"
        ):
            response = client.post(
                "/api/usuarios/",
                json={
                    "nombre": "Doctor Prueba",
                    "correo_electronico": "doctor.prueba@vitalia.com",
                    "password": "password123",
                    "rol_id_FK": 2,
                    "especialidad_id_FK": 1,
                    "numero_licencia": "LIC-TEST-001",
                    "costo_consulta": 500
                }
            )

        assert response.status_code == 201

        datos = response.json()

        assert datos["id_PK"] == 21
        assert datos["nombre"] == "Doctor Prueba"
        assert datos["rol_id_FK"] == 2
        assert datos["estado"] == "activo"

        objetos_agregados = [
            llamada.args[0]
            for llamada in db_falsa.add.call_args_list
        ]

        assert len(objetos_agregados) == 2

        doctor = next(
            objeto
            for objeto in objetos_agregados
            if objeto.__class__.__name__ == "Doctor"
        )

        assert doctor.usuario_id_FK == 21
        assert doctor.especialidad_id_FK == 1
        assert doctor.numero_licencia == "LIC-TEST-001"
        assert doctor.costo_consulta == 500
        assert doctor.estado == "activo"

    finally:
        app.dependency_overrides.clear()


def test_crear_usuario_paciente():
    """
    Comprueba que al crear un usuario con rol Paciente
    también se cree su registro de paciente.
    """

    rol = SimpleNamespace(
        id_PK=3,
        nombre="Paciente",
        esta_activo=True
    )

    db_falsa = crear_db_para_usuario(
        rol=rol,
        usuario_id=22
    )

    configurar_administrador(db_falsa)

    try:
        with patch(
            "app.routers.usuarios.generar_hash_password",
            return_value="hash-falso"
        ):
            response = client.post(
                "/api/usuarios/",
                json={
                    "nombre": "Maria",
                    "apellido": "Lopez",
                    "fecha_nacimiento": "2000-05-10",
                    "genero": "Femenino",
                    "telefono": "5512345678",
                    "direccion": "Ciudad de Mexico",
                    "correo_electronico": "maria.paciente@vitalia.com",
                    "password": "password123",
                    "rol_id_FK": 3
                }
            )

        assert response.status_code == 201

        datos = response.json()

        assert datos["id_PK"] == 22
        assert datos["nombre"] == "Maria"
        assert datos["rol_id_FK"] == 3
        assert datos["estado"] == "activo"

        objetos_agregados = [
            llamada.args[0]
            for llamada in db_falsa.add.call_args_list
        ]

        assert len(objetos_agregados) == 2

        paciente = next(
            objeto
            for objeto in objetos_agregados
            if objeto.__class__.__name__ == "Paciente"
        )

        assert paciente.usuario_id_FK == 22
        assert paciente.nombre == "Maria"
        assert paciente.apellido == "Lopez"
        assert paciente.telefono == "5512345678"
        assert paciente.direccion == "Ciudad de Mexico"
        assert paciente.estado == "activo"

    finally:
        app.dependency_overrides.clear()


def test_crear_usuario_correo_duplicado():
    """
    Comprueba que no se permita crear un usuario
    con un correo electrónico que ya existe.
    """

    usuario_existente = SimpleNamespace(
        id_PK=5,
        correo_electronico="existente@vitalia.com"
    )

    rol = SimpleNamespace(
        id_PK=1,
        nombre="Administrador",
        esta_activo=True
    )

    db_falsa = crear_db_para_usuario(
        correo_existente=usuario_existente,
        rol=rol
    )

    configurar_administrador(db_falsa)

    try:
        response = client.post(
            "/api/usuarios/",
            json={
                "nombre": "Usuario Repetido",
                "correo_electronico": "existente@vitalia.com",
                "password": "password123",
                "rol_id_FK": 1
            }
        )

        assert response.status_code == 400

        assert response.json()["detail"] == (
            "Ya existe un usuario con ese correo electrónico"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_usuario_rol_inexistente():
    """
    Comprueba que no se permita crear un usuario
    con un rol inexistente o inactivo.
    """

    db_falsa = crear_db_para_usuario(
        rol=None
    )

    configurar_administrador(db_falsa)

    try:
        response = client.post(
            "/api/usuarios/",
            json={
                "nombre": "Usuario Prueba",
                "correo_electronico": "rol.invalido@vitalia.com",
                "password": "password123",
                "rol_id_FK": 999
            }
        )

        assert response.status_code == 400

        assert response.json()["detail"] == (
            "El rol seleccionado no existe o está inactivo"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_paciente_sin_apellido():
    """
    Comprueba que un paciente no pueda crearse
    sin proporcionar apellido.
    """

    rol = SimpleNamespace(
        id_PK=3,
        nombre="Paciente",
        esta_activo=True
    )

    db_falsa = crear_db_para_usuario(
        rol=rol,
        usuario_id=23
    )

    configurar_administrador(db_falsa)

    try:
        with patch(
            "app.routers.usuarios.generar_hash_password",
            return_value="hash-falso"
        ):
            response = client.post(
                "/api/usuarios/",
                json={
                    "nombre": "Paciente",
                    "apellido": "",
                    "correo_electronico": "paciente.sin.apellido@vitalia.com",
                    "password": "password123",
                    "rol_id_FK": 3
                }
            )

        assert response.status_code == 400

        assert response.json()["detail"] == (
            "El apellido es obligatorio para pacientes"
        )

    finally:
        app.dependency_overrides.clear()


def test_crear_usuario_sin_permiso():
    """
    Comprueba que un usuario que no es administrador
    no pueda crear usuarios.
    """

    doctor = SimpleNamespace(
        id_PK=2,
        nombre="Doctor",
        correo_electronico="doctor@vitalia.com",
        rol_id_FK=2,
        estado="activo"
    )

    def obtener_doctor():
        return doctor

    app.dependency_overrides[get_current_user] = obtener_doctor

    try:
        response = client.post(
            "/api/usuarios/",
            json={
                "nombre": "Usuario Prueba",
                "correo_electronico": "sin.permiso@vitalia.com",
                "password": "password123",
                "rol_id_FK": 3
            }
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Solo el administrador puede crear usuarios"
        )

    finally:
        app.dependency_overrides.clear()