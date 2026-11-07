from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.usuario import Usuario
from app.schemas.superadmin import (
    AdministradorClinicaOut,
    ClinicaEstadoUpdate,
    ClinicaSuperadminOut,
    MetricasSuperadminOut,
    PlanClinicaOut,
    PlanSuperadminOut,
)


def exigir_superadmin(
    usuario_actual: Usuario = Depends(get_current_user),
) -> Usuario:
    if not usuario_actual.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requieren privilegios de Super Administrador",
        )
    return usuario_actual


router = APIRouter(
    prefix="/api/superadmin",
    tags=["SuperAdmin"],
    dependencies=[Depends(exigir_superadmin)],
)


@router.get("/clinicas", response_model=list[ClinicaSuperadminOut])
def listar_clinicas(
    db: Session = Depends(get_db),
):
    clinicas = (
        db.query(Clinica)
        .options(
            joinedload(Clinica.plan),
            selectinload(Clinica.usuarios),
            selectinload(Clinica.pacientes),
        )
        .order_by(Clinica.id_PK.desc())
        .all()
    )

    resultado = []
    for clinica in clinicas:
        admins = [
            AdministradorClinicaOut(
                id=u.id_PK,
                nombre_completo=f"{u.nombre} {u.apellido_paterno or ''}".strip(),
                correo_electronico=u.correo_electronico,
                estado=u.estado,
                ultimo_acceso=u.ultimo_acceso,
            )
            for u in clinica.usuarios
            if u.rol_id_FK == 1 or (u.rol and u.rol.nombre.strip().lower() in ["administrador", "admin", "superadmin"])
        ]

        plan_info = None
        if clinica.plan:
            plan_info = PlanClinicaOut(
                id=clinica.plan.id_PK,
                nombre=clinica.plan.nombre,
                precio_mensual=clinica.plan.precio_mensual,
                paypal_plan_id=clinica.plan.paypal_plan_id,
            )

        resultado.append(
            ClinicaSuperadminOut(
                id=clinica.id_PK,
                nombre_comercial=clinica.nombre_comercial,
                activa=clinica.activa,
                fecha_registro=clinica.fecha_registro,
                paypal_subscription_id=clinica.paypal_subscription_id,
                plan=plan_info,
                administradores=admins,
                total_usuarios=len(clinica.usuarios),
                total_pacientes=len(clinica.pacientes),
            )
        )

    return resultado


@router.patch("/clinicas/{id_clinica}/estado", response_model=ClinicaSuperadminOut)
def actualizar_estado_clinica(
    id_clinica: int,
    payload: ClinicaEstadoUpdate,
    db: Session = Depends(get_db),
):
    clinica = (
        db.query(Clinica)
        .options(
            joinedload(Clinica.plan),
            selectinload(Clinica.usuarios),
            selectinload(Clinica.pacientes),
        )
        .filter(Clinica.id_PK == id_clinica)
        .first()
    )

    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinica no encontrada",
        )

    clinica.activa = payload.activa
    db.commit()
    db.refresh(clinica)

    admins = [
        AdministradorClinicaOut(
            id=u.id_PK,
            nombre_completo=f"{u.nombre} {u.apellido_paterno or ''}".strip(),
            correo_electronico=u.correo_electronico,
            estado=u.estado,
            ultimo_acceso=u.ultimo_acceso,
        )
        for u in clinica.usuarios
        if u.rol_id_FK == 1 or (u.rol and u.rol.nombre.strip().lower() in ["administrador", "admin", "superadmin"])
    ]

    plan_info = None
    if clinica.plan:
        plan_info = PlanClinicaOut(
            id=clinica.plan.id_PK,
            nombre=clinica.plan.nombre,
            precio_mensual=clinica.plan.precio_mensual,
            paypal_plan_id=clinica.plan.paypal_plan_id,
        )

    return ClinicaSuperadminOut(
        id=clinica.id_PK,
        nombre_comercial=clinica.nombre_comercial,
        activa=clinica.activa,
        fecha_registro=clinica.fecha_registro,
        paypal_subscription_id=clinica.paypal_subscription_id,
        plan=plan_info,
        administradores=admins,
        total_usuarios=len(clinica.usuarios),
        total_pacientes=len(clinica.pacientes),
    )


@router.get("/metricas", response_model=MetricasSuperadminOut)
def obtener_metricas(
    db: Session = Depends(get_db),
):
    total_clinicas = db.query(Clinica).count()
    clinicas_activas = db.query(Clinica).filter(Clinica.activa.is_(True)).count()
    clinicas_inactivas = total_clinicas - clinicas_activas

    clinicas_con_plan = (
        db.query(Clinica)
        .options(joinedload(Clinica.plan))
        .filter(Clinica.activa.is_(True))
        .all()
    )

    ingresos_mensuales = sum(
        c.plan.precio_mensual for c in clinicas_con_plan if c.plan is not None
    )

    total_planes = db.query(PlanSuscripcion).count()
    total_usuarios = db.query(Usuario).count()

    return MetricasSuperadminOut(
        total_clinicas=total_clinicas,
        clinicas_activas=clinicas_activas,
        clinicas_inactivas=clinicas_inactivas,
        ingresos_mensuales=float(ingresos_mensuales),
        total_planes=total_planes,
        total_usuarios=total_usuarios,
    )


@router.get("/planes", response_model=list[PlanSuperadminOut])
def listar_planes(
    db: Session = Depends(get_db),
):
    planes = db.query(PlanSuscripcion).order_by(PlanSuscripcion.precio_mensual.asc()).all()

    conteo_por_plan = dict(
        db.query(Clinica.plan_id_FK, func.count(Clinica.id_PK))
        .filter(Clinica.activa.is_(True))
        .group_by(Clinica.plan_id_FK)
        .all()
    )

    return [
        PlanSuperadminOut(
            id=p.id_PK,
            nombre=p.nombre,
            precio_mensual=p.precio_mensual,
            precio_anual=p.precio_anual,
            limite_personal=p.limite_personal,
            limite_pacientes=p.limite_pacientes,
            incluye_calendar=p.incluye_calendar,
            incluye_correos=p.incluye_correos,
            limite_ia_mensual=p.limite_ia_mensual,
            paypal_plan_id=p.paypal_plan_id,
            clinicas_activas_count=conteo_por_plan.get(p.id_PK, 0),
        )
        for p in planes
    ]
