"""Turnos de sala que cruzan la medianoche (p. ej. 23:00 → 04:00 del día siguiente)."""
from datetime import time

import pytest

from app.core.horarios_sala import cruza_medianoche, cubre, duracion_min, se_traslapan, tramos

LUN, MAR, MIE, DOM = 0, 1, 2, 6


def test_cruza_medianoche():
    assert cruza_medianoche(time(23), time(4)) is True
    assert cruza_medianoche(time(22), time(0)) is True   # termina justo a las 00:00
    assert cruza_medianoche(time(9), time(17)) is False


def test_duracion():
    assert duracion_min(time(23), time(4)) == 5 * 60
    assert duracion_min(time(9), time(17)) == 8 * 60


def test_tramos_se_parten_en_la_medianoche():
    assert tramos(LUN, time(23), time(4)) == [(LUN, 23 * 60, 1440), (MAR, 0, 4 * 60)]
    assert tramos(DOM, time(23), time(4)) == [(DOM, 23 * 60, 1440), (LUN, 0, 4 * 60)]   # domingo → lunes
    assert tramos(None, time(23), time(4)) == [(None, 23 * 60, 1440), (None, 0, 4 * 60)]
    assert tramos(LUN, time(22), time(0)) == [(LUN, 22 * 60, 1440)]                    # sin tramo de madrugada


@pytest.mark.parametrize(
    "a,b,esperado",
    [
        # turno del lunes 23→04 ocupa la madrugada del martes
        ((LUN, time(23), time(4)), (MAR, time(2), time(3)), True),
        # …pero el martes a las 04:00 ya terminó
        ((LUN, time(23), time(4)), (MAR, time(4), time(8)), False),
        # …y el lunes por la mañana no choca
        ((LUN, time(23), time(4)), (LUN, time(8), time(12)), False),
        # lunes a las 23:30 sí choca
        ((LUN, time(23), time(4)), (LUN, time(23, 30), time(23, 59)), True),
        # dos turnos nocturnos el mismo día chocan
        ((LUN, time(22), time(2)), (LUN, time(23), time(5)), True),
        # nocturno lunes→martes y nocturno martes→miércoles encadenados: no chocan (24h en total)
        ((LUN, time(23), time(4)), (MAR, time(23), time(4)), False),
        # domingo por la noche ocupa el lunes por la madrugada
        ((DOM, time(23), time(4)), (LUN, time(1), time(2)), True),
        # «todos los días» nocturno choca con la madrugada de cualquier día
        ((None, time(23), time(4)), (MIE, time(3), time(5)), True),
        ((None, time(23), time(4)), (MIE, time(9), time(10)), False),
        # termina justo a la medianoche: no invade el día siguiente
        ((LUN, time(22), time(0)), (MAR, time(0), time(3)), False),
    ],
)
def test_traslapes_nocturnos(a, b, esperado):
    assert se_traslapan(*a, *b) is esperado
    assert se_traslapan(*b, *a) is esperado


def test_los_traslapes_diurnos_no_cambian():
    assert se_traslapan(0, time(9), time(11), 0, time(10), time(12)) is True
    assert se_traslapan(0, time(9), time(10), 0, time(10), time(12)) is False
    assert se_traslapan(0, time(9), time(11), 1, time(9), time(11)) is False


def test_cita_dentro_de_turno_nocturno():
    turno = (LUN, time(23), time(4))
    assert cubre(*turno, LUN, time(23, 15), time(23, 45)) is True      # antes de medianoche
    assert cubre(*turno, MAR, time(2), time(3)) is True                # madrugada siguiente
    assert cubre(*turno, MAR, time(3, 30), time(4, 30)) is False       # se pasa del fin del turno
    assert cubre(*turno, LUN, time(22), time(23, 30)) is False         # empieza antes del turno
    assert cubre(*turno, MAR, time(23, 30), time(23, 50)) is False     # el martes por la noche no es de este turno


def test_cita_dentro_de_turno_diurno_sigue_igual():
    turno = (LUN, time(9), time(14))
    assert cubre(*turno, LUN, time(10), time(11)) is True
    assert cubre(*turno, LUN, time(13), time(15)) is False
    assert cubre(*turno, MAR, time(10), time(11)) is False
    assert cubre(None, time(9), time(14), 3, time(10), time(11)) is True


def test_esquema_acepta_nocturno_y_rechaza_igual():
    pydantic = pytest.importorskip("pydantic")
    from app.schemas.doctor_sala import AsignacionNueva, AsignacionSala

    ok = AsignacionSala(sala_id_FK=1, dia_semana=0, hora_inicio=time(23), hora_fin=time(4))
    assert ok.hora_fin == time(4)
    AsignacionNueva(doctor_id=1, sala_id=1, dia_semana=0, hora_inicio=time(23), hora_fin=time(4))
    with pytest.raises(pydantic.ValidationError):
        AsignacionSala(sala_id_FK=1, dia_semana=0, hora_inicio=time(9), hora_fin=time(9))
