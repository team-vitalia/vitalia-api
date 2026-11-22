"""Pruebas de la importación/exportación del catálogo de medicamentos (sin base de datos)."""
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from app.services import medicamentos_io as mio


def _xlsx(filas: list[list]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_la_plantilla_se_puede_reimportar_tal_cual():
    filas = mio.leer_filas_excel(mio.plantilla_excel())
    assert len(filas) == 2
    for _, datos in filas:
        limpio, error = mio.normalizar_fila(datos)
        assert error is None
        assert limpio["tipo_articulo"] == "medicamento"


def test_exportar_y_reimportar_conserva_los_datos():
    meds = [{
        "nombre": "Ibuprofeno", "principio_activo": "Ibuprofeno", "presentacion": "400 mg",
        "categoria": "AINE", "tipo_articulo": "medicamento", "unidad_medida": "caja",
        "requiere_receta": True, "stock_minimo": 10, "codigo_barras": "0750123456789",
        "descripcion": "Antiinflamatorio", "stock_actual": 7,
    }]
    filas = mio.leer_filas_excel(mio.a_excel(meds))
    limpio, error = mio.normalizar_fila(filas[0][1])
    assert error is None
    assert limpio["nombre"] == "Ibuprofeno"
    assert limpio["requiere_receta"] is True
    assert limpio["stock_minimo"] == 10
    # el cero inicial del código de barras no se pierde
    assert limpio["codigo_barras"] == "0750123456789"


def test_codigo_de_barras_numerico_de_excel_no_queda_con_decimales():
    archivo = _xlsx([["Nombre", "Código de barras"], ["A", 7501234567890.0]])
    _, datos = mio.leer_filas_excel(archivo)[0]
    limpio, _ = mio.normalizar_fila(datos)
    assert limpio["codigo_barras"] == "7501234567890"


@pytest.mark.parametrize("fila,fragmento", [
    ({"nombre": ""}, "nombre es obligatorio"),
    ({"nombre": "X", "tipo_articulo": "raro"}, "Tipo"),
    ({"nombre": "X", "requiere_receta": "quizás"}, "Requiere receta"),
    ({"nombre": "X", "stock_minimo": "-3"}, "Stock mínimo"),
    ({"nombre": "X", "stock_minimo": "2.5"}, "Stock mínimo"),
    ({"nombre": "X" * 201}, "200"),
])
def test_filas_invalidas_reportan_el_motivo(fila, fragmento):
    limpio, error = mio.normalizar_fila(fila)
    assert limpio is None
    assert fragmento in error


def test_insumos_y_equipo_nunca_requieren_receta():
    limpio, _ = mio.normalizar_fila({"nombre": "Guantes", "tipo_articulo": "Insumos", "requiere_receta": "Sí"})
    assert limpio["tipo_articulo"] == "insumo"
    assert limpio["requiere_receta"] is False


def test_celdas_vacias_no_cuentan_como_presentes_para_actualizar():
    presentes = mio.campos_presentes({"nombre": "A", "categoria": "", "stock_minimo": None, "presentacion": "10 mg"})
    assert presentes == {"nombre", "presentacion"}


def test_archivo_sin_columna_nombre_o_vacio_se_rechaza():
    with pytest.raises(mio.ArchivoInvalido):
        mio.leer_filas_excel(b"")
    with pytest.raises(mio.ArchivoInvalido):
        mio.leer_filas_excel(b"esto no es un excel")
    with pytest.raises(mio.ArchivoInvalido):
        mio.leer_filas_excel(_xlsx([["Categoría"], ["Analgésico"]]))
    with pytest.raises(mio.ArchivoInvalido):
        mio.leer_filas_excel(_xlsx([["Nombre"]]))  # solo encabezado


def test_clave_de_duplicado_ignora_mayusculas_y_acentos():
    assert mio.clave_nombre("Ácido Fólico", " 5 MG ") == mio.clave_nombre("acido folico", "5 mg")


def test_pdf_y_excel_con_lista_vacia_no_fallan():
    assert mio.a_pdf([], "Clínica & Co").startswith(b"%PDF")
    libro = load_workbook(BytesIO(mio.a_excel([])))
    assert libro.sheetnames == ["Medicamentos"]
