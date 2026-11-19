"""Textos en lenguaje sencillo para la auditoría (campos, valores y cambios).

Se usa tanto al GUARDAR descripciones nuevas como al EXPLICAR registros viejos,
para que quien revise la auditoría no necesite saber de bases de datos.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

ETIQUETAS_CAMPO: dict[str, str] = {
    "nombre": "Nombre",
    "tipo": "Tipo",
    "ubicacion": "Ubicación",
    "estado": "Estado",
    "capacidad": "Capacidad (personas)",
    "piso": "Piso",
    "lista_equipamiento": "Resumen de equipamiento",
    "nombre_equipo": "Nombre del equipo",
    "tipo_equipo": "Tipo de equipo",
    "numero_serie": "Número de serie",
    "fecha_compra": "Fecha de compra",
    "ultimo_mantenimiento": "Último mantenimiento",
    "proximo_mantenimiento": "Próximo mantenimiento",
    "stock_actual": "Existencias",
    "numero_lote": "Lote",
    "fecha_vencimiento": "Fecha de caducidad",
    "fecha_recepcion": "Fecha de recepción",
    "precio_venta": "Precio de venta",
    "medicamento_id_FK": "Artículo",
    "proveedor_id_FK": "Proveedor",
    "sala_id_FK": "Sala",
    "doctor_id_FK": "Doctor",
    "paciente_id_FK": "Paciente",
    "paciente_id": "Paciente",
    "doctor_id": "Doctor",
    "fecha": "Fecha",
    "hora_inicio": "Hora de inicio",
    "hora_fin": "Hora de fin",
    "motivo": "Motivo",
    "prioridad": "Prioridad",
    "citas_reasignadas": "Citas reasignadas",
    "conflictos": "Conflictos",
    "origen": "Doctor de origen",
    "destino": "Doctor de destino",
    "horizonte_dias": "Días analizados",
    "requiere_equipo": "Requiere equipo",
    "cie10": "Diagnóstico (CIE-10)",
    "medicamentos": "Medicamentos",
    "interacciones_confirmadas": "Interacciones confirmadas",
}

# Campos técnicos que no aportan nada a una persona sin conocimientos de sistemas
CAMPOS_OCULTOS = {"id_PK", "clinica_id_FK", "clinica_id", "origen_ia", "hash_firma"}

VALORES_TEXTO: dict[str, str] = {
    "disponible": "Disponible",
    "ocupada": "Ocupada",
    "mantenimiento": "En mantenimiento",
    "inactiva": "Inactiva",
    "operativo": "Funcionando",
    "fuera_de_servicio": "Fuera de servicio",
    "diagnostico": "Diagnóstico",
    "monitoreo": "Monitoreo",
    "cirugia": "Cirugía",
    "soporte_vital": "Soporte vital",
    "laboratorio": "Laboratorio",
    "esterilizacion": "Esterilización",
    "mobiliario": "Mobiliario",
    "otro": "Otro",
    "normal": "Normal",
    "alta": "Alta",
    "baja": "Baja",
    "urgente": "Urgente",
    "programada": "Programada",
    "completada": "Completada",
    "cancelada": "Cancelada",
}


def etiqueta_campo(campo: str) -> str:
    if campo in ETIQUETAS_CAMPO:
        return ETIQUETAS_CAMPO[campo]
    t = campo.replace("_FK", "").replace("_id", "").replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def _fecha_texto(valor: str) -> str | None:
    """Convierte 2026-11-05 o 2026-11-05T10:00:00 en 05/11/2026."""
    try:
        if len(valor) >= 10 and valor[4] == "-" and valor[7] == "-":
            d = valor[:10].split("-")
            return f"{d[2]}/{d[1]}/{d[0]}"
    except Exception:  # pragma: no cover - defensivo
        return None
    return None


def valor_legible(valor: Any) -> str:
    if valor is None or valor == "":
        return "vacío"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, (list, tuple)):
        return ", ".join(valor_legible(v) for v in valor) or "vacío"
    if isinstance(valor, dict):
        return ", ".join(f"{etiqueta_campo(k)}: {valor_legible(v)}" for k, v in valor.items())
    if isinstance(valor, str):
        if valor in VALORES_TEXTO:
            return VALORES_TEXTO[valor]
        f = _fecha_texto(valor)
        return f or valor
    return str(valor)


def lista_cambios(antes: dict | None, despues: dict | None, solo_cambiados: bool = True) -> list[dict]:
    """Devuelve [{campo, etiqueta, antes, despues}] ya en lenguaje sencillo."""
    antes = antes or {}
    despues = despues or {}
    salida: list[dict] = []
    for campo in list(dict.fromkeys([*antes.keys(), *despues.keys()])):
        if campo in CAMPOS_OCULTOS or campo.endswith("_FK"):
            continue  # números internos: no le dicen nada a quien revisa
        a, d = antes.get(campo), despues.get(campo)
        if solo_cambiados and valor_legible(a) == valor_legible(d):
            continue
        if not solo_cambiados and a in (None, "") and d in (None, ""):
            continue
        salida.append(
            {
                "campo": campo,
                "etiqueta": etiqueta_campo(campo),
                "antes": valor_legible(a),
                "despues": valor_legible(d),
            }
        )
    return salida


def frase_cambios(antes: dict | None, despues: dict | None, maximo: int = 4) -> str:
    """'capacidad de 3 a 5, piso de 1 a 2' (para descripciones guardadas)."""
    cambios = lista_cambios(antes, despues)
    if not cambios:
        return "sin cambios en los datos"
    partes = [f"{c['etiqueta'].lower()} de «{c['antes']}» a «{c['despues']}»" for c in cambios[:maximo]]
    if len(cambios) > maximo:
        partes.append(f"y {len(cambios) - maximo} dato(s) más")
    return ", ".join(partes)
