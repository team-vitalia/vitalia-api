from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.doctor import Doctor
from app.models.cita import Cita
from app.models.consulta import Consulta

client = TestClient(app)

# --- FUNCIONES AUXILIARES ---
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

# ==========================================
# PR-032: Consulta de agenda médica
# ==========================================
def test_consulta_agenda_medica():
    """
    El sistema debe retornar el listado de citas programadas 
    asociadas al ID del médico.
    """
    doctor = crear_usuario_prueba(10, "Alex", 2)
    
    doctor_db = SimpleNamespace(id_PK=1, usuario_id_FK=10, nombre="Alex")
    
    cita_simulada = SimpleNamespace(
        id_PK=1, paciente_id_FK=1, doctor_id_FK=1, 
        fecha=date.today(), hora_inicio="10:00:00", hora_fin="10:30:00", 
        estado="programada", motivo="Dolor", notas="", creado_por=10
    )

    db_falsa = MagicMock()
    # Simulamos que encuentra al doctor
    db_falsa.query.return_value.filter.return_value.first.return_value = doctor_db
    # CORRECCIÓN: La cadena correcta es filter -> order_by -> all
    db_falsa.query.return_value.filter.return_value.order_by.return_value.all.return_value = [cita_simulada]

    configurar_dependencias(doctor, db_falsa)

    try:
        response = client.get("/api/citas/mis-consultas")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["estado"] == "programada"
    finally:
        app.dependency_overrides.clear()


# ==========================================
# PR-033: Consultar expediente clínico (Ya pasó, no se toca)
# ==========================================
def test_consultar_expediente_clinico():
    doctor = crear_usuario_prueba(10, "Alex", 2)
    doctor_db = SimpleNamespace(id_PK=1, usuario_id_FK=10)
    cita_db = SimpleNamespace(id_PK=1, paciente_id_FK=1, doctor_id_FK=1, fecha=date.today(), hora_inicio="10:00:00", hora_fin="10:30:00", estado="programada", motivo="Dolor", notas="")
    paciente_db = SimpleNamespace(id_PK=1, nombre="Carlos", apellido="Slim", fecha_nacimiento=date(1985,10,20), telefono="555", usuario=None)

    db_falsa = MagicMock()
    db_falsa.query.return_value.filter.return_value.first.side_effect = [cita_db, doctor_db, paciente_db]
    db_falsa.query.return_value.options.return_value.filter.return_value.all.return_value = []

    configurar_dependencias(doctor, db_falsa)

    try:
        response = client.get("/api/citas/1")
        assert response.status_code == 200
        datos = response.json()
        assert datos["paciente"]["nombre"] == "Carlos"
        assert datos["paciente"]["apellido"] == "Slim"
    finally:
        app.dependency_overrides.clear()

# ==========================================
# PR-034: Registrar consulta
# ==========================================
def test_registrar_consulta():
    """
    El sistema debe guardar el diagnóstico, notas y 
    tratamiento con estatus HTTP 201.
    """
    doctor = crear_usuario_prueba(10, "Alex", 2)
    
    doctor_db = SimpleNamespace(id_PK=1, usuario_id_FK=10)
    cita_db = SimpleNamespace(id_PK=1, doctor_id_FK=1, estado="programada")

    db_falsa = MagicMock()
    
    # SOLUCIÓN: Usamos el nombre de la clase para que nunca falle la comparación
    def mock_query(modelo):
        mock = MagicMock()
        nombre_modelo = getattr(modelo, '__name__', str(modelo))
        
        if 'Doctor' in nombre_modelo:
            mock.filter.return_value.first.return_value = doctor_db
        elif 'Cita' in nombre_modelo:
            mock.filter.return_value.first.return_value = cita_db
        elif 'Consulta' in nombre_modelo:
            mock.filter.return_value.first.return_value = None
        return mock

    db_falsa.query.side_effect = mock_query

    configurar_dependencias(doctor, db_falsa)

    payload = {
        "cita_id_FK": 1,
        "paciente_id_FK": 1,
        "diagnostico": "Fiebre alta",
        "tratamiento": "Paracetamol",
        "notas": "Reposo"
    }

    try:
        response = client.post("/api/consultas/", json=payload)
        
        # Si falla, imprimimos el error real para saber qué pasó
        if response.status_code != 201:
            print("\n[DEBUG] Error del servidor:", response.json())
            
        assert response.status_code == 201
        datos = response.json()
        assert datos["diagnostico"] == "Fiebre alta"
        assert db_falsa.add.call_count > 0 
        assert db_falsa.commit.call_count == 1
    finally:
        app.dependency_overrides.clear()

# ==========================================
# PR-035: Actualizar expediente (Alergias) (Ya pasó, no se toca)
# ==========================================
def test_actualizar_expediente_alergias():
    doctor = crear_usuario_prueba(10, "Alex", 2)
    paciente_db = SimpleNamespace(id_PK=1, nombre="Carlos")

    db_falsa = MagicMock()
    db_falsa.query.return_value.filter.return_value.first.side_effect = [paciente_db, None]

    configurar_dependencias(doctor, db_falsa)

    payload = {
        "nombre": "Penicilina",
        "severidad": "grave",
        "notas": "Alergia detectada en consulta"
    }

    try:
        response = client.post("/api/pacientes/1/alergias", json=payload)
        assert response.status_code == 200
        assert response.json()["mensaje"] == "Alergia agregada correctamente al expediente"
        assert db_falsa.add.call_count > 0
        assert db_falsa.commit.call_count == 1
    finally:
        app.dependency_overrides.clear()


        # ==========================================
# PR-004: Login / Datos faltantes
# ==========================================
def test_login_sin_datos():
    """
    PR-004: El sistema debe validar los campos obligatorios 
    y rechazar una solicitud sin los datos necesarios.
    """
    # Enviamos un JSON vacío al endpoint de login
    response = client.post("/api/auth/login", json={})

    # FastAPI devuelve automáticamente un código 422 (Unprocessable Entity)
    # cuando faltan datos obligatorios definidos en el esquema de Pydantic.
    assert response.status_code == 422
    
    datos_error = response.json()
    assert "detail" in datos_error