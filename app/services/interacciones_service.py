"""Revisión de interacciones medicamentosas y posibles alergias.

IMPORTANTE: son avisos de apoyo basados en el catálogo `interacciones_medicamentos`
y en las alergias registradas del paciente. No sustituyen la valoración ni la
decisión de un profesional de la salud; el catálogo debe cargarse con información
clínica validada por los responsables clínicos.
"""
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.alergia import Alergia
from app.models.alergia_paciente import AlergiaPaciente
from app.models.interaccion_medicamento import InteraccionMedicamento

# Severidades que bloquean la receta hasta que el médico confirme explícitamente.
SEVERIDADES_GRAVES = {
    "grave", "alta", "severa", "contraindicada", "contraindicado",
    "critica", "crítica", "mayor", "major", "severe", "high",
}


def es_grave(severidad: str | None) -> bool:
    return (severidad or "").strip().lower() in SEVERIDADES_GRAVES


def evaluar_interacciones(db: Session, medicamentos_ids: list[int]) -> list[dict]:
    """Devuelve las interacciones registradas entre los medicamentos indicados."""
    ids = list(dict.fromkeys(medicamentos_ids))
    if len(ids) < 2:
        return []

    interacciones = db.query(InteraccionMedicamento).filter(
        or_(
            and_(
                InteraccionMedicamento.medicamento_id_FK.in_(ids),
                InteraccionMedicamento.medicamento_interactuante_id_FK.in_(ids),
            )
        )
    ).all()

    detalles = []
    for inter in interacciones:
        nombre_1 = (
            inter.medicamento.nombre
            if (inter.medicamento and hasattr(inter.medicamento, "nombre"))
            else f"Medicamento ID {inter.medicamento_id_FK}"
        )
        nombre_2 = (
            inter.medicamento_interactuante.nombre
            if (inter.medicamento_interactuante and hasattr(inter.medicamento_interactuante, "nombre"))
            else f"Medicamento ID {inter.medicamento_interactuante_id_FK}"
        )
        detalles.append(
            {
                "medicamento_1": nombre_1,
                "medicamento_2": nombre_2,
                "severidad": inter.severidad or "No especificada",
                "descripcion": inter.descripcion or "Interacción detectada entre medicamentos.",
                "nivel_evidencia": inter.nivel_evidencia,
                "accion_requerida": inter.accion_requerida,
            }
        )
    return detalles


def alertas_alergias(db: Session, paciente_id: int, medicamentos: list) -> list[dict]:
    """Posibles coincidencias entre alergias del paciente y nombre/principio activo.

    Es una coincidencia de texto (no un catálogo clínico): se muestra como
    «posible alergia» para que el médico la verifique.
    """
    alergias = (
        db.query(Alergia.nombre)
        .join(AlergiaPaciente, AlergiaPaciente.alergia_id_FK == Alergia.id_PK)
        .filter(AlergiaPaciente.paciente_id_FK == paciente_id)
        .all()
    )
    alertas = []
    for (nombre_alergia,) in alergias:
        clave = (nombre_alergia or "").strip().lower()
        if len(clave) < 3:
            continue
        for med in medicamentos:
            texto = f"{med.nombre or ''} {med.principio_activo or ''}".lower()
            if clave in texto:
                alertas.append(
                    {
                        "medicamento": med.nombre,
                        "alergia": nombre_alergia,
                        "mensaje": (
                            f"El paciente tiene registrada la alergia «{nombre_alergia}» "
                            f"y podría relacionarse con {med.nombre}. Verifícalo antes de recetar."
                        ),
                    }
                )
    return alertas
