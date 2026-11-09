from datetime import datetime, timedelta
import calendar
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.clinica import Clinica
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.registro_auditoria import RegistroAuditoria
from app.models.usuario import Usuario
from app.schemas.superadmin import (
    AdministradorClinicaOut,
    AuditoriaAccesoOut,
    AuditoriaActividadOut,
    ClinicaEstadoUpdate,
    ClinicaPlanUpdate,
    ClinicaSuperadminOut,
    MetricaItemMes,
    MetricasClinicaIndividualOut,
    MetricasSuperadminOut,
    PlanClinicaOut,
    PlanSuperadminOut,
    UsoRecursoOut,
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


def _armar_plan_info(plan: PlanSuscripcion | None) -> PlanClinicaOut | None:
    if not plan:
        return None
    return PlanClinicaOut(
        id=plan.id_PK,
        nombre=plan.nombre,
        precio_mensual=plan.precio_mensual,
        precio_anual=plan.precio_anual,
        limite_personal=plan.limite_personal,
        limite_pacientes=plan.limite_pacientes,
        paypal_plan_id=plan.paypal_plan_id,
    )


def _armar_admins(usuarios: list[Usuario]) -> list[AdministradorClinicaOut]:
    return [
        AdministradorClinicaOut(
            id=u.id_PK,
            nombre_completo=f"{u.nombre} {u.apellido_paterno or ''}".strip(),
            correo_electronico=u.correo_electronico,
            estado=u.estado,
            ultimo_acceso=u.ultimo_acceso,
        )
        for u in usuarios
        if u.rol_id_FK == 1 or (u.rol and u.rol.nombre and u.rol.nombre.strip().lower() in ["administrador", "admin", "superadmin"])
    ]


@router.get("/clinicas", response_model=list[ClinicaSuperadminOut])
def listar_clinicas(
    db: Session = Depends(get_db),
):
    clinicas = (
        db.query(Clinica)
        .options(
            joinedload(Clinica.plan),
            selectinload(Clinica.usuarios).joinedload(Usuario.rol),
            selectinload(Clinica.pacientes),
        )
        .order_by(Clinica.id_PK.desc())
        .all()
    )

    resultado = []
    for clinica in clinicas:
        admins = _armar_admins(clinica.usuarios)
        plan_info = _armar_plan_info(clinica.plan)

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


@router.get("/clinicas/{id_clinica}", response_model=ClinicaSuperadminOut)
def obtener_clinica_por_id(
    id_clinica: int,
    db: Session = Depends(get_db),
):
    clinica = (
        db.query(Clinica)
        .options(
            joinedload(Clinica.plan),
            selectinload(Clinica.usuarios).joinedload(Usuario.rol),
            selectinload(Clinica.pacientes),
        )
        .filter(Clinica.id_PK == id_clinica)
        .first()
    )

    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada",
        )

    admins = _armar_admins(clinica.usuarios)
    plan_info = _armar_plan_info(clinica.plan)

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
            selectinload(Clinica.usuarios).joinedload(Usuario.rol),
            selectinload(Clinica.pacientes),
        )
        .filter(Clinica.id_PK == id_clinica)
        .first()
    )

    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada",
        )

    clinica.activa = payload.activa
    db.commit()
    db.refresh(clinica)

    admins = _armar_admins(clinica.usuarios)
    plan_info = _armar_plan_info(clinica.plan)

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


@router.patch("/clinicas/{id_clinica}/plan", response_model=ClinicaSuperadminOut)
def actualizar_plan_clinica(
    id_clinica: int,
    payload: ClinicaPlanUpdate,
    db: Session = Depends(get_db),
):
    clinica = (
        db.query(Clinica)
        .filter(Clinica.id_PK == id_clinica)
        .first()
    )
    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada",
        )

    nuevo_plan = db.query(PlanSuscripcion).filter(PlanSuscripcion.id_PK == payload.plan_id).first()
    if not nuevo_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El plan especificado no existe",
        )

    clinica.plan_id_FK = nuevo_plan.id_PK
    db.commit()

    return obtener_clinica_por_id(id_clinica=id_clinica, db=db)


@router.get("/clinicas/{id_clinica}/metricas", response_model=MetricasClinicaIndividualOut)
def obtener_metricas_clinica(
    id_clinica: int,
    db: Session = Depends(get_db),
):
    clinica = (
        db.query(Clinica)
        .options(
            joinedload(Clinica.plan),
            selectinload(Clinica.usuarios).joinedload(Usuario.rol),
            selectinload(Clinica.pacientes),
        )
        .filter(Clinica.id_PK == id_clinica)
        .first()
    )

    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada",
        )

    total_personal = len(clinica.usuarios)
    limite_personal = clinica.plan.limite_personal if clinica.plan else 5
    pct_personal = round(min(100.0, (total_personal / max(limite_personal, 1)) * 100), 1)

    total_pacientes = len(clinica.pacientes)
    limite_pacientes = clinica.plan.limite_pacientes if clinica.plan else 50
    pct_pacientes = round(min(100.0, (total_pacientes / max(limite_pacientes, 1)) * 100), 1)

    nombre_plan_lower = (clinica.plan.nombre if clinica.plan else "").lower()
    if "corp" in nombre_plan_lower or "enterprise" in nombre_plan_lower:
        limite_storage_mb = 20480.0
    elif "pro" in nombre_plan_lower:
        limite_storage_mb = 10240.0
    elif "clínica" in nombre_plan_lower or "clinica" in nombre_plan_lower:
        limite_storage_mb = 5120.0
    else:
        limite_storage_mb = 2048.0

    almacenamiento_usado_mb = round(min(limite_storage_mb, (total_pacientes * 12.5) + (total_personal * 6.0) + 40.0), 1)
    pct_storage = round(min(100.0, (almacenamiento_usado_mb / limite_storage_mb) * 100), 1)

    hoy = datetime.now()
    inicio_mes_actual = datetime(hoy.year, hoy.month, 1)
    if hoy.month == 12:
        inicio_mes_siguiente = datetime(hoy.year + 1, 1, 1)
    else:
        inicio_mes_siguiente = datetime(hoy.year, hoy.month + 1, 1)

    if hoy.month == 1:
        inicio_mes_anterior = datetime(hoy.year - 1, 12, 1)
    else:
        inicio_mes_anterior = datetime(hoy.year, hoy.month - 1, 1)

    citas_mes_actual = (
        db.query(Cita)
        .filter(
            Cita.clinica_id_FK == id_clinica,
            Cita.fecha >= inicio_mes_actual.date(),
            Cita.fecha < inicio_mes_siguiente.date(),
        )
        .count()
    )

    citas_mes_anterior = (
        db.query(Cita)
        .filter(
            Cita.clinica_id_FK == id_clinica,
            Cita.fecha >= inicio_mes_anterior.date(),
            Cita.fecha < inicio_mes_actual.date(),
        )
        .count()
    )

    dia_aniversario = clinica.fecha_registro.day if clinica.fecha_registro else 1
    max_dias_mes_actual = calendar.monthrange(hoy.year, hoy.month)[1]
    dia_efectivo = min(dia_aniversario, max_dias_mes_actual)

    if hoy.day < dia_efectivo:
        proximo_ciclo = datetime(hoy.year, hoy.month, dia_efectivo)
    else:
        if hoy.month == 12:
            prox_year = hoy.year + 1
            prox_month = 1
        else:
            prox_year = hoy.year
            prox_month = hoy.month + 1
        max_dias_prox = calendar.monthrange(prox_year, prox_month)[1]
        proximo_ciclo = datetime(prox_year, prox_month, min(dia_aniversario, max_dias_prox))

    motivos_upsell = []
    if pct_pacientes >= 80.0:
        motivos_upsell.append(f"Pacientes al {pct_pacientes}% de capacidad ({total_pacientes}/{limite_pacientes})")
    if pct_personal >= 80.0:
        motivos_upsell.append(f"Personal administrativo al {pct_personal}% de capacidad ({total_personal}/{limite_personal})")
    if pct_storage >= 80.0:
        motivos_upsell.append(f"Almacenamiento al {pct_storage}% ({almacenamiento_usado_mb} MB / {limite_storage_mb} MB)")

    candidato_upsell = len(motivos_upsell) > 0

    if not clinica.activa:
        estado_suscripcion = "SUSPENDIDA"
    elif clinica.paypal_subscription_id:
        estado_suscripcion = "ACTIVA (PAYPAL)"
    else:
        estado_suscripcion = "ACTIVA (DIRECTA)"

    usuarios_ordenados = sorted(
        clinica.usuarios,
        key=lambda u: (u.ultimo_acceso is not None, u.ultimo_acceso or datetime.min),
        reverse=True,
    )
    ultimos_accesos = [
        AuditoriaAccesoOut(
            usuario_id=u.id_PK,
            nombre_usuario=f"{u.nombre} {u.apellido_paterno or ''}".strip(),
            rol=u.rol.nombre if u.rol and u.rol.nombre else "Usuario",
            correo=u.correo_electronico,
            ultimo_acceso=u.ultimo_acceso,
        )
        for u in usuarios_ordenados[:6]
    ]

    registros_auditoria = (
        db.query(RegistroAuditoria)
        .join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK)
        .filter(Usuario.clinica_id_FK == id_clinica)
        .order_by(RegistroAuditoria.marca_tiempo.desc())
        .limit(8)
        .all()
    )

    actividades_recientes = [
        AuditoriaActividadOut(
            id=ra.id_PK,
            usuario=f"{ra.usuario.nombre} {ra.usuario.apellido_paterno or ''}".strip() if ra.usuario else "Sistema",
            accion=ra.accion or "Acción",
            descripcion=ra.descripcion,
            marca_tiempo=ra.marca_tiempo,
            nombre_tabla=ra.nombre_tabla,
        )
        for ra in registros_auditoria
    ]

    return MetricasClinicaIndividualOut(
        clinica_id=clinica.id_PK,
        nombre_comercial=clinica.nombre_comercial,
        activa=clinica.activa,
        fecha_registro=clinica.fecha_registro,
        plan=_armar_plan_info(clinica.plan),
        paypal_subscription_id=clinica.paypal_subscription_id,
        estado_suscripcion=estado_suscripcion,
        proximo_ciclo_facturacion=proximo_ciclo,
        citas_mes_actual=citas_mes_actual,
        citas_mes_anterior=citas_mes_anterior,
        uso_personal=UsoRecursoOut(
            actual=float(total_personal),
            limite=float(limite_personal),
            porcentaje=pct_personal,
            unidad="usuarios",
        ),
        uso_pacientes=UsoRecursoOut(
            actual=float(total_pacientes),
            limite=float(limite_pacientes),
            porcentaje=pct_pacientes,
            unidad="pacientes",
        ),
        uso_almacenamiento=UsoRecursoOut(
            actual=almacenamiento_usado_mb,
            limite=limite_storage_mb,
            porcentaje=pct_storage,
            unidad="MB",
        ),
        candidato_upsell=candidato_upsell,
        motivos_upsell=motivos_upsell,
        administradores=_armar_admins(clinica.usuarios),
        ultimos_accesos=ultimos_accesos,
        actividades_recientes=actividades_recientes,
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
    proyeccion_anual = round(float(ingresos_mensuales) * 12.0, 2)

    total_planes = db.query(PlanSuscripcion).count()
    total_usuarios = db.query(Usuario).count()
    usuarios_activos = db.query(Usuario).filter(Usuario.estado == "activo").count()

    hoy = datetime.now()
    inicio_mes_actual = datetime(hoy.year, hoy.month, 1)

    if hoy.month == 1:
        inicio_mes_anterior = datetime(hoy.year - 1, 12, 1)
    else:
        inicio_mes_anterior = datetime(hoy.year, hoy.month - 1, 1)

    usuarios_nuevos_mes = (
        db.query(Usuario)
        .filter(Usuario.creado_en >= inicio_mes_actual)
        .count()
    )
    usuarios_mes_anterior = (
        db.query(Usuario)
        .filter(Usuario.creado_en >= inicio_mes_anterior, Usuario.creado_en < inicio_mes_actual)
        .count()
    )

    if usuarios_mes_anterior > 0:
        tasa_crecimiento_usuarios = round(((usuarios_nuevos_mes - usuarios_mes_anterior) / usuarios_mes_anterior) * 100.0, 1)
    else:
        tasa_crecimiento_usuarios = 100.0 if usuarios_nuevos_mes > 0 else 0.0

    nombres_meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    historico_6_meses: list[MetricaItemMes] = []

    for i in range(5, -1, -1):
        target_year = hoy.year
        target_month = hoy.month - i
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        mes_start = datetime(target_year, target_month, 1)
        if target_month == 12:
            mes_end = datetime(target_year + 1, 1, 1)
        else:
            mes_end = datetime(target_year, target_month + 1, 1)

        nuevas_clinicas_mes = (
            db.query(Clinica)
            .filter(Clinica.fecha_registro >= mes_start, Clinica.fecha_registro < mes_end)
            .count()
        )

        nuevos_usuarios_mes = (
            db.query(Usuario)
            .filter(Usuario.creado_en >= mes_start, Usuario.creado_en < mes_end)
            .count()
        )

        clinicas_activas_en_mes = (
            db.query(Clinica)
            .options(joinedload(Clinica.plan))
            .filter(Clinica.fecha_registro < mes_end, Clinica.activa.is_(True))
            .all()
        )
        ingresos_mes = sum(
            c.plan.precio_mensual for c in clinicas_activas_en_mes if c.plan is not None
        )

        etiqueta_mes = f"{nombres_meses[target_month - 1]} {str(target_year)[2:]}"

        historico_6_meses.append(
            MetricaItemMes(
                mes=etiqueta_mes,
                ingresos=float(ingresos_mes),
                nuevas_clinicas=nuevas_clinicas_mes,
                nuevos_usuarios=nuevos_usuarios_mes,
            )
        )

    return MetricasSuperadminOut(
        total_clinicas=total_clinicas,
        clinicas_activas=clinicas_activas,
        clinicas_inactivas=clinicas_inactivas,
        ingresos_mensuales=float(ingresos_mensuales),
        proyeccion_anual=proyeccion_anual,
        total_planes=total_planes,
        total_usuarios=total_usuarios,
        usuarios_activos=usuarios_activos,
        usuarios_nuevos_mes=usuarios_nuevos_mes,
        tasa_crecimiento_usuarios=tasa_crecimiento_usuarios,
        historico_6_meses=historico_6_meses,
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
