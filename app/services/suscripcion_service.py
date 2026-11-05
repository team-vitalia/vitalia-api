from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.usuario import Usuario


def obtener_clinica_con_plan(db: Session, clinica_id: int) -> tuple[Clinica, PlanSuscripcion]:
    clinica = db.query(Clinica).filter(Clinica.id_PK == clinica_id).first()
    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada"
        )

    if not clinica.activa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La clínica se encuentra inactiva"
        )

    plan = clinica.plan
    if not plan:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.id_PK == clinica.plan_id_FK
        ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan de suscripción no encontrado"
        )

    return clinica, plan


def validar_limite_personal(db: Session, clinica_id: int) -> None:
    _, plan = obtener_clinica_con_plan(db, clinica_id)

    total_personal = (
        db.query(Usuario)
        .filter(Usuario.clinica_id_FK == clinica_id)
        .count()
    )

    if total_personal >= plan.limite_personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Límite de personal alcanzado para el plan {plan.nombre}. Máximo permitido: {plan.limite_personal}"
        )


def validar_limite_pacientes(db: Session, clinica_id: int) -> None:
    _, plan = obtener_clinica_con_plan(db, clinica_id)

    total_pacientes = (
        db.query(Paciente)
        .filter(Paciente.clinica_id_FK == clinica_id)
        .count()
    )

    if total_pacientes >= plan.limite_pacientes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Límite de pacientes alcanzado para el plan {plan.nombre}. Máximo permitido: {plan.limite_pacientes}"
        )
