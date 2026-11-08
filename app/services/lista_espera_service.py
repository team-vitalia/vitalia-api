"""Lógica de la lista de espera de citas."""
from datetime import datetime

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.lista_espera import ListaEspera
from app.services.notificacion_service import NotificacionService

ACTIVOS = ("en_espera", "notificado")


def orden_prioridad():
    return case(
        (ListaEspera.prioridad == "urgente", 0),
        (ListaEspera.prioridad == "alta", 1),
        else_=2,
    )


def candidatos_activos(db: Session, clinica_id: int | None):
    q = db.query(ListaEspera).filter(ListaEspera.estado == "en_espera")
    if clinica_id is not None:
        q = q.filter(ListaEspera.clinica_id_FK == clinica_id)
    return q.order_by(orden_prioridad(), ListaEspera.creado_en.asc())


def notificar_siguiente_en_espera(db: Session, clinica_id: int | None, doctor_id: int | None) -> ListaEspera | None:
    """Cuando se libera un horario, avisa al primer paciente que esperaba.

    Prioriza a quien espera a ese doctor; si no hay, a quien espera su especialidad
    o a «cualquier doctor». Devuelve la entrada notificada (o None).
    """
    doctor = db.query(Doctor).filter(Doctor.id_PK == doctor_id).first() if doctor_id else None
    candidatos = candidatos_activos(db, clinica_id).all()

    def aplica(e: ListaEspera) -> bool:
        if e.doctor_id_FK is not None:
            return e.doctor_id_FK == doctor_id
        if e.especialidad_id_FK is not None:
            return bool(doctor and doctor.especialidad_id_FK == e.especialidad_id_FK)
        return True

    elegido = next((e for e in candidatos if aplica(e)), None)
    if not elegido:
        return None

    elegido.estado = "notificado"
    db.commit()
    paciente = elegido.paciente
    if paciente and paciente.usuario_id_FK:
        try:
            NotificacionService(db).crear(
                paciente.usuario_id_FK,
                "Se liberó un espacio para tu cita. Comunícate con recepción para confirmarlo.",
                tipo="waitlist_available",
                enlace="/paciente",
            )
        except Exception:  # noqa: BLE001
            pass
    return elegido
