"""Reglas de traslape del calendario de salas (lógica pura, sin base de datos)."""
from datetime import time

import pytest

from app.services.asignacion_salas_service import cuando, hhmm, se_traslapan


@pytest.mark.parametrize(
    "a,b,esperado",
    [
        # mismo día, horas que se cruzan
        ((0, time(9), time(11)), (0, time(10), time(12)), True),
        # mismo día, una termina justo cuando empieza la otra: NO chocan
        ((0, time(9), time(10)), (0, time(10), time(12)), False),
        # días distintos: no chocan aunque las horas coincidan
        ((0, time(9), time(11)), (1, time(9), time(11)), False),
        # «todos los días» choca con cualquier día si las horas se cruzan
        ((None, time(9), time(11)), (3, time(10), time(12)), True),
        ((None, time(9), time(11)), (3, time(11), time(12)), False),
        # un bloque dentro de otro
        ((2, time(8), time(14)), (2, time(10), time(11)), True),
    ],
)
def test_se_traslapan(a, b, esperado):
    assert se_traslapan(*a, *b) is esperado
    assert se_traslapan(*b, *a) is esperado  # es simétrico


def test_textos_legibles():
    assert hhmm(time(9, 5)) == "09:05"
    assert cuando(0, time(9), time(13)) == "el lunes de 09:00 a 13:00"
    assert cuando(None, time(8), time(10)) == "todos los días de 08:00 a 10:00"
