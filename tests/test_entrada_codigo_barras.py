"""Entrada de mercancía por código de barras (servicio + reglas de lote/caducidad).

Usa SQLite en memoria con las tablas reales del almacén, sin tocar tu base MySQL.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registra todos los modelos para resolver relaciones)
from app.database.connection import Base
from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.models.movimiento_inventario import MovimientoInventario
from app.models.tipo_movimiento_inventario import TipoMovimientoInventario
from app.services import inventario_service as inv

MANANA = date.today() + timedelta(days=1)
EN_UN_ANIO = date.today() + timedelta(days=365)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            Medicamento.__table__,
            Inventario.__table__,
            MovimientoInventario.__table__,
            TipoMovimientoInventario.__table__,
        ],
    )
    sesion = sessionmaker(bind=engine)()
    yield sesion
    sesion.close()


def _producto(db, codigo="7501234567890", tipo="medicamento", clinica=1, nombre="Paracetamol 500 mg"):
    med = Medicamento(nombre=nombre, codigo_barras=codigo, tipo_articulo=tipo, clinica_id_FK=clinica)
    db.add(med)
    db.commit()
    return med


def test_codigo_inexistente_404_con_mensaje_claro(db):
    _producto(db)
    with pytest.raises(inv.InventarioError) as e:
        inv.resolver_codigo_barras(db, "0000000000000", clinica_id=1)
    assert e.value.status_code == 404
    assert "No existe ningún producto" in e.value.detalle


def test_codigo_de_otra_clinica_no_se_ve(db):
    _producto(db, clinica=2)
    with pytest.raises(inv.InventarioError) as e:
        inv.resolver_codigo_barras(db, "7501234567890", clinica_id=1)
    assert e.value.status_code == 404


def test_encuentra_aunque_el_lector_agregue_ceros_o_salto_de_linea(db):
    med = _producto(db)
    encontrado, _ = inv.resolver_codigo_barras(db, "07501234567890\r\n", clinica_id=1)
    assert encontrado.id_PK == med.id_PK


def test_codigo_duplicado_en_catalogo_409(db):
    _producto(db, nombre="A")
    _producto(db, nombre="B")
    with pytest.raises(inv.InventarioError) as e:
        inv.resolver_codigo_barras(db, "7501234567890", clinica_id=1)
    assert e.value.status_code == 409


def test_primera_entrada_crea_lote_y_movimiento(db):
    med = _producto(db)
    r = inv.registrar_entrada_por_codigo(db, med, 24, 1, numero_lote="L1", fecha_vencimiento=EN_UN_ANIO)
    db.commit()
    assert r["lote_nuevo"] is True
    assert r["stock_lote_anterior"] == 0 and r["stock_lote_nuevo"] == 24
    assert r["stock_total"] == 24
    mov = db.query(MovimientoInventario).one()
    assert mov.cantidad == 24 and mov.stock_anterior == 0 and mov.stock_nuevo == 24
    assert db.query(TipoMovimientoInventario).one().nombre == inv.TIPO_ENTRADA


def test_mismo_lote_y_caducidad_suma_al_lote_existente(db):
    med = _producto(db)
    inv.registrar_entrada_por_codigo(db, med, 10, 1, numero_lote="L1", fecha_vencimiento=EN_UN_ANIO)
    r = inv.registrar_entrada_por_codigo(db, med, 5, 1, numero_lote="l1", fecha_vencimiento=EN_UN_ANIO)
    db.commit()
    assert r["lote_nuevo"] is False
    assert r["stock_lote_anterior"] == 10 and r["stock_lote_nuevo"] == 15
    assert db.query(Inventario).count() == 1
    assert db.query(MovimientoInventario).count() == 2


def test_lote_distinto_crea_otro_lote_y_el_stock_total_suma(db):
    med = _producto(db)
    inv.registrar_entrada_por_codigo(db, med, 10, 1, numero_lote="L1", fecha_vencimiento=EN_UN_ANIO)
    r = inv.registrar_entrada_por_codigo(db, med, 7, 1, numero_lote="L2", fecha_vencimiento=EN_UN_ANIO)
    db.commit()
    assert r["lote_nuevo"] is True
    assert r["stock_total"] == 17
    assert db.query(Inventario).count() == 2


def test_mismo_lote_con_otra_caducidad_409(db):
    med = _producto(db)
    inv.registrar_entrada_por_codigo(db, med, 10, 1, numero_lote="L1", fecha_vencimiento=EN_UN_ANIO)
    with pytest.raises(inv.InventarioError) as e:
        inv.registrar_entrada_por_codigo(db, med, 5, 1, numero_lote="L1", fecha_vencimiento=MANANA)
    assert e.value.status_code == 409


def test_medicamento_exige_lote_y_caducidad(db):
    med = _producto(db)
    with pytest.raises(inv.InventarioError) as e:
        inv.registrar_entrada_por_codigo(db, med, 5, 1)
    assert e.value.status_code == 422


def test_no_acepta_caducidad_pasada_ni_cantidad_invalida(db):
    med = _producto(db)
    ayer = date.today() - timedelta(days=1)
    with pytest.raises(inv.InventarioError):
        inv.registrar_entrada_por_codigo(db, med, 5, 1, numero_lote="L1", fecha_vencimiento=ayer)
    with pytest.raises(inv.InventarioError):
        inv.registrar_entrada_por_codigo(db, med, 0, 1, numero_lote="L1", fecha_vencimiento=EN_UN_ANIO)


def test_insumo_no_exige_lote_y_suma_en_el_mismo_registro_sin_lote(db):
    guantes = _producto(db, codigo="GUANTES-M", tipo="insumo", nombre="Guantes M")
    inv.registrar_entrada_por_codigo(db, guantes, 100, 1)
    r = inv.registrar_entrada_por_codigo(db, guantes, 50, 1)
    db.commit()
    assert r["lote_nuevo"] is False
    assert r["stock_lote_nuevo"] == 150
    assert db.query(Inventario).count() == 1