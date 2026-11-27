"""Aritmética de horarios de sala, incluidos los turnos que cruzan la medianoche.

Un horario es (dia_semana, hora_inicio, hora_fin):
  * dia_semana: 0 = lunes ... 6 = domingo; None = todos los días.
  * Si hora_fin <= hora_inicio el turno CRUZA la medianoche y termina al día siguiente
    (p. ej. 23:00 → 04:00, o 22:00 → 00:00). hora_fin == hora_inicio no es válido.

Para comparar horarios todo se parte en «tramos» dentro de un mismo día: (dia, minuto_ini, minuto_fin)
con 0 <= minuto_ini < minuto_fin <= 1440. Un turno nocturno del lunes 23:00→04:00 son dos tramos:
(lunes, 23:00, 24:00) y (martes, 00:00, 04:00). Este módulo no depende de la base de datos.
"""
from __future__ import annotations

from datetime import time

MIN_DIA = 24 * 60

Tramo = tuple[int | None, int, int]


def a_min(t: time) -> int:
    return t.hour * 60 + t.minute


def cruza_medianoche(ini: time, fin: time) -> bool:
    """True si el turno termina al día siguiente (fin <= inicio)."""
    return a_min(fin) <= a_min(ini)


def dia_siguiente(dia: int | None) -> int | None:
    return None if dia is None else (dia + 1) % 7


def duracion_min(ini: time, fin: time) -> int:
    d = a_min(fin) - a_min(ini)
    return d if d > 0 else d + MIN_DIA


def tramos(dia: int | None, ini: time | None, fin: time | None) -> list[Tramo]:
    """Parte un horario en tramos que no cruzan la medianoche."""
    i = 0 if ini is None else a_min(ini)
    f = MIN_DIA if fin is None else a_min(fin)
    if f > i:
        return [(dia, i, f)]
    # Cruza la medianoche: hasta las 24:00 de hoy y desde las 00:00 de mañana
    partes: list[Tramo] = [(dia, i, MIN_DIA)]
    if f > 0:
        partes.append((dia_siguiente(dia), 0, f))
    return partes


def _chocan(a: Tramo, b: Tramo) -> bool:
    if a[0] is not None and b[0] is not None and a[0] != b[0]:
        return False
    return a[1] < b[2] and b[1] < a[2]


def se_traslapan(dia_a, ini_a: time, fin_a: time, dia_b, ini_b: time, fin_b: time) -> bool:
    """Dos horarios chocan si alguno de sus tramos coincide en día (o «todos los días») y en horas."""
    return any(_chocan(x, y) for x in tramos(dia_a, ini_a, fin_a) for y in tramos(dia_b, ini_b, fin_b))


def cubre(dia_bloque, ini_bloque: time | None, fin_bloque: time | None, dia_cita: int, ini_cita: time, fin_cita: time) -> bool:
    """True si un horario asignado cubre por completo una cita (la cita puede caer en la madrugada del turno)."""
    del_bloque = tramos(dia_bloque, ini_bloque, fin_bloque)
    for d, i, f in tramos(dia_cita, ini_cita, fin_cita):
        if not any((td is None or td == d) and ti <= i and f <= tf for td, ti, tf in del_bloque):
            return False
    return True
