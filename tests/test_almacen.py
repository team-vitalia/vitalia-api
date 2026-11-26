import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import date
from types import SimpleNamespace

from app.core.config import settings
from app.database.connection import get_db
from app.routers.almacen import router
from app.core.dependencies import get_current_user
from app.models.medicamento import Medicamento
from app.schemas.almacen import EvaluacionInteraccionesIA, InteraccionIAPrediccion
from app.services.groq_service import GroqClinicalService

mock_user = MagicMock()
mock_user.id_PK = 1
mock_user.clinica_id_FK = None
mock_user.rol_id_FK = 1

app = FastAPI()
app.include_router(router)

mock_session = MagicMock()

def override_get_db():
    yield mock_session

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: mock_user
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mock_session():
    """Limpia el estado del mock antes de ejecutar cada test."""
    mock_session.reset_mock()


# -----------------------------------------------------------------------------
# TEST 1: Listar Medicamentos (GET /api/almacen/medicamentos)
# -----------------------------------------------------------------------------
def test_listar_medicamentos_exito():
    mock_med = MagicMock()
    mock_med.id_PK = 1
    mock_med.nombre = "Paracetamol"
    mock_med.principio_activo = "Paracetamol"
    mock_med.presentacion = "Comprimido 500mg"
    mock_med.requiere_receta = False
    mock_med.descripcion = "Analgésico"
    mock_med.codigo_barras = "7501234567890"
    mock_med.categoria = "Analgésicos"
    mock_med.tipo_articulo = "medicamento"
    mock_med.unidad_medida = "tableta"
    mock_med.stock_minimo = 10

    mock_session.query.return_value.all.return_value = [mock_med]

    response = client.get("/api/almacen/medicamentos")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id_PK"] == 1
    assert data[0]["nombre"] == "Paracetamol"


# -----------------------------------------------------------------------------
# TEST 2: Listar Inventario (GET /api/almacen/inventario)
# -----------------------------------------------------------------------------
def test_listar_inventario_exito():
    mock_item = MagicMock()
    mock_item.id_PK = 10
    mock_item.medicamento_id_FK = 1
    mock_item.numero_lote = "LOTE-2026-A"
    mock_item.stock_actual = 100
    mock_item.ubicacion = "Estante A1"
    mock_item.fecha_vencimiento = date(2027, 12, 31)
    mock_item.precio_venta = 15.50
    mock_item.proveedor_id_FK = 2
    mock_item.fecha_recepcion = date(2026, 1, 15)

    mock_session.query.return_value.all.return_value = [mock_item]

    response = client.get("/api/almacen/inventario")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id_PK"] == 10
    assert data[0]["numero_lote"] == "LOTE-2026-A"
    assert data[0]["stock_actual"] == 100


# -----------------------------------------------------------------------------
# TEST 3: Registrar Lote en Inventario (POST /api/almacen/inventario)
# -----------------------------------------------------------------------------
def test_registrar_lote_inventario_exito():
    payload = {
        "medicamento_id_FK": 1,
        "numero_lote": "LOTE-999",
        "stock_actual": 50,
        "ubicacion": "Bodega B",
        "fecha_vencimiento": "2028-06-30",
        "precio_venta": 25.0,
        "proveedor_id_FK": 1,
        "fecha_recepcion": "2026-03-10"
    }

    # Asigna la ID requerida por el schema al ejecutar db.refresh()
    def fake_refresh(obj):
        obj.id_PK = 5

    mock_session.refresh.side_effect = fake_refresh

    response = client.post("/api/almacen/inventario", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["id_PK"] == 5
    assert data["numero_lote"] == "LOTE-999"
    assert data["stock_actual"] == 50
    assert mock_session.add.called is True
    assert mock_session.commit.called is True


# -----------------------------------------------------------------------------
# TEST 4: Evaluar Interacciones - Sin interacciones (< 2 IDs)
# -----------------------------------------------------------------------------
def test_evaluar_interacciones_menos_de_dos_ids():
    payload = {"medicamentos_ids": [1]}

    response = client.post("/api/almacen/evaluar-interacciones", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["tiene_interaccion"] is False
    assert data["detalles"] == []


# -----------------------------------------------------------------------------
# TEST 5: Evaluar Interacciones - Detección con éxito de interacción
# -----------------------------------------------------------------------------
def test_evaluar_interacciones_con_resultado():
    payload = {"medicamentos_ids": [1, 2]}

    mock_interaccion = MagicMock()
    mock_interaccion.medicamento_id_FK = 1
    mock_interaccion.medicamento_interactuante_id_FK = 2
    mock_interaccion.severidad = "Alta"
    mock_interaccion.descripcion = "Riesgo de hemorragia"
    mock_interaccion.nivel_evidencia = "Confirmado"
    mock_interaccion.accion_requerida = "Evitar combinación"

    mock_interaccion.medicamento = MagicMock(nombre="Warfarina")
    mock_interaccion.medicamento_interactuante = MagicMock(nombre="Aspirina")

    mock_session.query.return_value.filter.return_value.all.return_value = [mock_interaccion]

    response = client.post("/api/almacen/evaluar-interacciones", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["tiene_interaccion"] is True
    assert len(data["detalles"]) == 1
    assert data["detalles"][0]["medicamento_1"] == "Warfarina"
    assert data["detalles"][0]["medicamento_2"] == "Aspirina"
    assert data["detalles"][0]["severidad"] == "Alta"


def preparar_medicamentos_para_ia():
    mock_session.query.side_effect = None
    mock_user.clinica_id_FK = 10
    mock_user.clinica = SimpleNamespace(
        plan=SimpleNamespace(limite_ia_mensual=50),
    )
    primero = MagicMock(
        id_PK=1,
        nombre="DEMO Warfarina",
        principio_activo="Warfarina",
        presentacion="Tableta demo",
    )
    segundo = MagicMock(
        id_PK=2,
        nombre="DEMO Naproxeno",
        principio_activo="Naproxeno",
        presentacion="Tableta demo",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = [
        primero,
        segundo,
    ]


def test_evaluar_interacciones_ia_con_resultado(monkeypatch):
    preparar_medicamentos_para_ia()

    async def fake_analisis(self, medicamentos):
        assert [m["principio_activo"] for m in medicamentos] == [
            "Warfarina",
            "Naproxeno",
        ]
        return EvaluacionInteraccionesIA(
            detalles=[
                InteraccionIAPrediccion(
                    medicamento_1="Warfarina",
                    medicamento_2="Naproxeno",
                    severidad="incierta",
                    descripcion="Resultado simulado para comprobar el contrato de la API.",
                )
            ],
            observaciones="Resultado de prueba; no usar para atención clínica.",
        )

    monkeypatch.setattr(
        GroqClinicalService,
        "analizar_interacciones_medicamentos",
        fake_analisis,
    )
    response = client.post(
        "/api/almacen/evaluar-interacciones-ia",
        json={"medicamentos_ids": [1, 2]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tiene_interaccion"] is True
    assert data["fuente"] == "Groq IA"
    assert data["detalles"][0]["accion_requerida"]
    assert "sustituye" in data["aviso"].lower()


def test_evaluar_interacciones_ia_rechaza_plan_sin_ia():
    mock_user.clinica = SimpleNamespace(
        plan=SimpleNamespace(limite_ia_mensual=0),
    )
    response = client.post(
        "/api/almacen/evaluar-interacciones-ia",
        json={"medicamentos_ids": [1, 2]},
    )

    assert response.status_code == 403
    assert "no incluye análisis con IA" in response.json()["detail"]


def test_evaluar_interacciones_ia_informa_clave_no_configurada(monkeypatch):
    preparar_medicamentos_para_ia()
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    response = client.post(
        "/api/almacen/evaluar-interacciones-ia",
        json={"medicamentos_ids": [1, 2]},
    )

    assert response.status_code == 503
    assert "no está configurada" in response.json()["detail"]