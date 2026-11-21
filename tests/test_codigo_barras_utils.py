"""Pruebas de las utilidades puras de código de barras (no necesitan base de datos)."""
from datetime import date

from app.core.codigo_barras import normalizar_codigo, parsear_gs1, variantes_codigo


def test_normalizar_quita_espacios_y_saltos_de_linea_del_lector():
    assert normalizar_codigo(" 7501234567890\r\n") == "7501234567890"
    assert normalizar_codigo(None) == ""
    assert normalizar_codigo("   ") == ""


def test_variantes_ean13_upca_y_gtin14_son_el_mismo_producto():
    assert "07501234567890" in variantes_codigo("7501234567890")      # EAN-13 -> GTIN-14
    assert "7501234567890" in variantes_codigo("07501234567890")      # GTIN-14 -> EAN-13
    v = variantes_codigo("012345678905")                              # UPC-A
    assert "0012345678905" in v and "12345678905" in v


def test_variantes_codigos_no_numericos_no_se_alteran():
    assert variantes_codigo("ABC-123") == ["ABC-123"]
    assert variantes_codigo("0000") == ["0000"]
    assert variantes_codigo("") == []


def test_gs1_con_parentesis():
    g = parsear_gs1("(01)07501234567890(17)271231(10)L2411A")
    assert g == {"gtin": "07501234567890", "lote": "L2411A", "caducidad": date(2027, 12, 31)}


def test_gs1_dia_cero_es_ultimo_dia_del_mes_y_separador_gs():
    g = parsear_gs1("0107501234567890" "17271200" "10LOTE9" "\x1d" "21SERIE1")
    assert g["caducidad"] == date(2027, 12, 31)
    assert g["lote"] == "LOTE9"


def test_gs1_solo_gtin():
    assert parsear_gs1("0107501234567890") == {"gtin": "07501234567890", "lote": None, "caducidad": None}


def test_gs1_lote_ambiguo_se_omite_en_lugar_de_adivinarlo():
    g = parsear_gs1("0107501234567890" "17271230" "10ESTELOTEESDEMASIADOLARGOPARAGS1")
    assert g["lote"] is None
    assert g["caducidad"] == date(2027, 12, 30)


def test_codigo_comun_no_es_gs1():
    assert parsear_gs1("7501234567890") is None
    assert parsear_gs1("") is None
    assert parsear_gs1(None) is None


def test_gs1_fecha_invalida_se_ignora():
    assert parsear_gs1("0107501234567890" "17991399")["caducidad"] is None