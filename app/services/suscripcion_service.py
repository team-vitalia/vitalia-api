from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.usuario import Usuario

ROL_ID_PACIENTE = 3


def obtener_clinica_con_plan(db: Session, clinica_id: int) -> tuple[Clinica, PlanSuscripcion]:
    stmt_clinica = select(Clinica).where(Clinica.id_PK == clinica_id)
    clinica = db.scalar(stmt_clinica)
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
        stmt_plan = select(PlanSuscripcion).where(
            PlanSuscripcion.id_PK == clinica.plan_id_FK
        )
        plan = db.scalar(stmt_plan)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan de suscripción no encontrado"
        )

    return clinica, plan


def verificar_limite_personal(db: Session, clinica_id: int) -> None:
    _, plan = obtener_clinica_con_plan(db, clinica_id)

    stmt_personal = select(func.count(Usuario.id_PK)).where(
        Usuario.clinica_id_FK == clinica_id,
        Usuario.rol_id_FK != ROL_ID_PACIENTE
    )
    total_personal = db.scalar(stmt_personal) or 0

    if total_personal >= plan.limite_personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Límite de personal alcanzado para el plan {plan.nombre}. Máximo permitido: {plan.limite_personal}"
        )


def verificar_limite_pacientes(db: Session, clinica_id: int) -> None:
    _, plan = obtener_clinica_con_plan(db, clinica_id)

    es_gratuito = (plan.nombre or "").strip().lower() == "gratuito"
    limite_mes = getattr(plan, "limite_pacientes_mes", None)

    if es_gratuito or limite_mes is not None:
        max_mes = limite_mes if limite_mes is not None else 20
        ahora = datetime.now()
        inicio_mes = datetime(ahora.year, ahora.month, 1)
        if ahora.month == 12:
            fin_mes = datetime(ahora.year + 1, 1, 1)
        else:
            fin_mes = datetime(ahora.year, ahora.month + 1, 1)

        stmt_pacientes_mes = select(func.count(Paciente.id_PK)).where(
            Paciente.clinica_id_FK == clinica_id,
            Paciente.creado_en >= inicio_mes,
            Paciente.creado_en < fin_mes,
        )
        total_pacientes_mes = db.scalar(stmt_pacientes_mes) or 0

        stmt_usuarios_pac_mes = select(func.count(Usuario.id_PK)).where(
            Usuario.clinica_id_FK == clinica_id,
            Usuario.rol_id_FK == ROL_ID_PACIENTE,
            Usuario.creado_en >= inicio_mes,
            Usuario.creado_en < fin_mes,
        )
        total_usuarios_pac_mes = db.scalar(stmt_usuarios_pac_mes) or 0

        total_mes = max(total_pacientes_mes, total_usuarios_pac_mes)

        if total_mes >= max_mes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Límite de pacientes mensual alcanzado para el plan {plan.nombre}. Máximo permitido: {max_mes} al mes."
            )

    if not es_gratuito:
        stmt_pacientes = select(func.count(Paciente.id_PK)).where(
            Paciente.clinica_id_FK == clinica_id
        )
        total_pacientes_tabla = db.scalar(stmt_pacientes) or 0

        stmt_usuarios_paciente = select(func.count(Usuario.id_PK)).where(
            Usuario.clinica_id_FK == clinica_id,
            Usuario.rol_id_FK == ROL_ID_PACIENTE
        )
        total_pacientes_usuarios = db.scalar(stmt_usuarios_paciente) or 0

        total_pacientes = max(total_pacientes_tabla, total_pacientes_usuarios)

        if total_pacientes >= plan.limite_pacientes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Límite de pacientes alcanzado para el plan {plan.nombre}. Máximo permitido: {plan.limite_pacientes}"
            )


validar_limite_personal = verificar_limite_personal
validar_limite_pacientes = verificar_limite_pacientes
