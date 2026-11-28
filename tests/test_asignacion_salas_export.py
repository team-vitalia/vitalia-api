"""Exportación (Excel / PDF) del resumen de asignación de salas."""
from datetime import date, time
from io import BytesIO

from app.services import asignacion_salas_export as ex


def _datos():
    salas = [{"id": 1, "nombre": "Consultorio 1", "tipo": "Consultorio", "piso": "1", "estado": "disponible"},
             {"id": 2, "nombre": "Sala libre", "tipo": None, "piso": None, "estado": "disponible"}]
    doctores = [{"id": 10, "nombre": "Dra. Ana", "especialidad": "Cardiología"},
                {"id": 11, "nombre": "Dr. Sin Sala", "especialidad": None}]
    asig = [
        dict(id_PK=1, doctor_id=10, doctor_nombre="Dra. Ana", especialidad="Cardiología", sala_id=1, sala_nombre="Consultorio 1",
             sala_tipo="Consultorio", sala_piso="1", sala_estado="disponible", dia_semana=0, hora_inicio=time(23), hora_fin=time(4)),
        dict(id_PK=2, doctor_id=10, doctor_nombre="Dra. Ana", especialidad="Cardiología", sala_id=1, sala_nombre="Consultorio 1",
             sala_tipo="Consultorio", sala_piso="1", sala_estado="disponible", dia_semana=None, hora_inicio=time(9), hora_fin=time(13)),
    ]
    return {"salas": salas, "doctores": doctores, "asignaciones": asig}


def test_excel_tiene_las_hojas_y_los_turnos_nocturnos():
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(ex.a_excel(_datos(), "Clínica Demo", date(2026, 11, 23))))
    assert wb.sheetnames == ["Resumen", "Asignaciones", "Semana por sala", "Semana por doctor"]

    semana = wb["Semana por sala"]
    assert semana["B5"].value == "Lun 23/11"
    lunes, martes = semana["B6"].value, semana["C6"].value
    assert "23:00–24:00 (sigue mañana)" in lunes
    assert "00:00–04:00 (viene de ayer)" in martes
    assert "09:00–13:00" in lunes and "09:00–13:00" in martes   # «todos los días» aparece en cada día

    detalle = wb["Asignaciones"]
    filas = {detalle[f"F{r}"].value: (detalle[f"J{r}"].value, detalle[f"K{r}"].value) for r in (6, 7)}
    assert filas["Todos los días"] == ("Matutino", "No")
    turno, cruza = filas["Lunes"]
    assert turno == "Nocturno" and cruza.startswith("Sí")           # el nocturno cruza la medianoche


def test_resumen_cuenta_horas_y_pendientes():
    filas = ex._filas(_datos())
    kpis = dict(ex._kpis(_datos(), filas))
    assert kpis["Asignaciones registradas"] == "2"
    assert kpis["Horas de sala por semana"] == "33.0 h"              # 5 h (nocturno) + 4 h × 7 días
    salas, docs = ex._sin_asignar(_datos(), filas)
    assert [s["nombre"] for s in salas] == ["Sala libre"]
    assert [d["nombre"] for d in docs] == ["Dr. Sin Sala"]


def test_pdf_y_vacios_no_fallan():
    assert ex.a_pdf(_datos(), "Clínica Demo", date(2026, 11, 23)).startswith(b"%PDF")
    vacio = {"salas": [], "doctores": [], "asignaciones": []}
    assert ex.a_pdf(vacio).startswith(b"%PDF")
    assert len(ex.a_excel(vacio)) > 1000
