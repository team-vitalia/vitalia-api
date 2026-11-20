from datetime import datetime, timedelta
import calendar
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_current_user
from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import get_db
from app.models.aviso_superadmin import AvisoSuperadmin
from app.models.cancelacion_suscripcion import CancelacionSuscripcion
from app.models.cita import Cita
from app.models.clinica import Clinica
from app.models.notificacion import Notificacion
from app.models.paciente import Paciente
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.registro_auditoria import RegistroAuditoria
from app.models.usuario import Usuario
from app.services.connection_manager import manager
from app.utils.auditoria import registrar_auditoria
from app.schemas.superadmin import (
    AdministradorClinicaOut,
    AuditoriaAccesoOut,
    AuditoriaActividadOut,
    AuditoriaPaginadaOut,
    AuditoriaRegistroDetalleOut,
    AvisoSuperadminCrear,
    AvisoSuperadminOut,
    CancelacionItemOut,
    CancelacionesSuperadminOut,
    ClinicaEstadoUpdate,
    ClinicaExcepcionesOut,
    ClinicaExcepcionesUpdate,
    ClinicaPlanUpdate,
    ClinicaSuperadminOut,
    DesbloquearResponse,
    ImpersonarResponse,
    MetricaItemMes,
    MetricasClinicaIndividualOut,
    MetricasSuperadminOut,
    PlanClinicaOut,
    PlanSuperadminOut,
    ResetPasswordResponse,
    ResumenAuditoriaOut,
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
    limite_personal_base = clinica.plan.limite_personal if clinica.plan else 5
    limite_personal = limite_personal_base + (getattr(clinica, "limite_personal_extra", 0) or 0)
    pct_personal = round(min(100.0, (total_personal / max(limite_personal, 1)) * 100), 1)

    total_pacientes = len(clinica.pacientes)
    limite_pacientes_base = clinica.plan.limite_pacientes if clinica.plan else 50
    limite_pacientes = limite_pacientes_base + (getattr(clinica, "limite_pacientes_extra", 0) or 0)
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
        excepciones=ClinicaExcepcionesOut(
            limite_pacientes_extra=getattr(clinica, "limite_pacientes_extra", 0) or 0,
            limite_personal_extra=getattr(clinica, "limite_personal_extra", 0) or 0,
            dias_gracia=getattr(clinica, "dias_gracia", 0) or 0,
            fecha_fin_gracia=getattr(clinica, "fecha_fin_gracia", None),
            motivo_excepcion=getattr(clinica, "motivo_excepcion", None),
        ),
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


@router.get("/cancelaciones", response_model=CancelacionesSuperadminOut)
def listar_cancelaciones(
    db: Session = Depends(get_db),
):
    registros = (
        db.query(CancelacionSuscripcion)
        .options(
            joinedload(CancelacionSuscripcion.clinica),
            joinedload(CancelacionSuscripcion.plan_anterior),
        )
        .order_by(CancelacionSuscripcion.fecha_cancelacion.desc())
        .all()
    )

    total_cancelaciones = len(registros)
    total_reembolsos_procesados = sum(1 for r in registros if r.estado_reembolso == "PROCESADO")

    motivos_conteo: dict[str, int] = {}
    estados_reembolso_conteo: dict[str, int] = {}

    items = []
    for r in registros:
        cat = r.motivo_categoria or "OTRO"
        motivos_conteo[cat] = motivos_conteo.get(cat, 0) + 1

        est = r.estado_reembolso or "NO_APLICA"
        estados_reembolso_conteo[est] = estados_reembolso_conteo.get(est, 0) + 1

        nombre_clinica = r.clinica.nombre_comercial if r.clinica else "Clínica"
        nombre_plan = r.plan_anterior.nombre if r.plan_anterior else "Plan de Pago"

        items.append(
            CancelacionItemOut(
                id=r.id_PK,
                clinica_id=r.clinica_id_FK,
                nombre_clinica=nombre_clinica,
                plan_anterior_id=r.plan_anterior_id_FK,
                nombre_plan_anterior=nombre_plan,
                fecha_cancelacion=r.fecha_cancelacion,
                motivo_categoria=r.motivo_categoria,
                comentarios_adicionales=r.comentarios_adicionales,
                aplica_reembolso=r.aplica_reembolso,
                estado_reembolso=r.estado_reembolso,
                paypal_refund_id=r.paypal_refund_id,
            )
        )

    return CancelacionesSuperadminOut(
        total_cancelaciones=total_cancelaciones,
        total_reembolsos_procesados=total_reembolsos_procesados,
        motivos_conteo=motivos_conteo,
        estados_reembolso_conteo=estados_reembolso_conteo,
        cancelaciones=items,
    )


@router.post("/clinicas/{id_clinica}/impersonar", response_model=ImpersonarResponse)
def impersonar_clinica(
    id_clinica: int,
    usuario_id: int | None = None,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    if usuario_id:
        usuario = (
            db.query(Usuario)
            .filter(Usuario.id_PK == usuario_id, Usuario.clinica_id_FK == id_clinica)
            .first()
        )
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado en la clínica")
    else:
        usuario = (
            db.query(Usuario)
            .filter(Usuario.clinica_id_FK == id_clinica, Usuario.rol_id_FK == 1)
            .first()
        )
        if not usuario:
            usuario = db.query(Usuario).filter(Usuario.clinica_id_FK == id_clinica).first()
        if not usuario:
            raise HTTPException(status_code=400, detail="La clínica no tiene usuarios registrados para impersonar")

    token = crear_access_token(
        data={
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK,
            "clinica_id": usuario.clinica_id_FK,
            "is_impersonated": True,
            "impersonated_by": superadmin.id_PK,
        },
        clinica_id=usuario.clinica_id_FK,
        expires_delta=timedelta(hours=2),
    )

    registrar_auditoria(
        db,
        superadmin,
        "IMPERSONACION_SOPORTE",
        "usuarios",
        usuario.id_PK,
        None,
        {"usuario_impersonado": usuario.id_PK, "clinica_id": id_clinica},
        descripcion=f"Superadmin {superadmin.correo_electronico} inició sesión en modo soporte como {usuario.correo_electronico} de {clinica.nombre_comercial}",
    )
    db.commit()

    rol_nombre = usuario.rol.nombre if usuario.rol and usuario.rol.nombre else "Usuario"
    return ImpersonarResponse(
        access_token=token,
        token_type="bearer",
        usuario_id=usuario.id_PK,
        nombre=f"{usuario.nombre} {usuario.apellido_paterno or ''}".strip(),
        correo=usuario.correo_electronico,
        rol=rol_nombre,
        clinica_id=clinica.id_PK,
        nombre_clinica=clinica.nombre_comercial,
    )


@router.post("/clinicas/{id_clinica}/reset-password-titular", response_model=ResetPasswordResponse)
def reset_password_titular(
    id_clinica: int,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    titular = (
        db.query(Usuario)
        .filter(Usuario.clinica_id_FK == id_clinica, Usuario.rol_id_FK == 1)
        .first()
    )
    if not titular:
        titular = db.query(Usuario).filter(Usuario.clinica_id_FK == id_clinica).first()
    if not titular:
        raise HTTPException(status_code=400, detail="La clínica no tiene usuarios registrados")

    caracteres = string.ascii_letters + string.digits + "!@#$%"
    temp_pass = "Vit@" + "".join(secrets.choice(caracteres) for _ in range(8)) + "1"

    titular.hash_contrasena = generar_hash_password(temp_pass)
    titular.estado = "activo"
    registrar_auditoria(
        db,
        superadmin,
        "RESET_PASSWORD_ADMINISTRADOR",
        "usuarios",
        titular.id_PK,
        None,
        {"correo": titular.correo_electronico, "clinica_id": id_clinica},
        descripcion=f"Superadmin restableció la contraseña de acceso del administrador {titular.correo_electronico}",
    )
    db.commit()

    return ResetPasswordResponse(
        mensaje="Contraseña temporal generada exitosamente. Proporciónala al titular de forma segura.",
        correo=titular.correo_electronico,
        password_temporal=temp_pass,
    )


@router.post("/clinicas/{id_clinica}/desbloquear-titular", response_model=DesbloquearResponse)
def desbloquear_titular(
    id_clinica: int,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    usuarios = db.query(Usuario).filter(Usuario.clinica_id_FK == id_clinica).all()
    for u in usuarios:
        u.estado = "activo"

    registrar_auditoria(
        db,
        superadmin,
        "DESBLOQUEO_CUENTAS_CLINICA",
        "clinicas",
        id_clinica,
        None,
        {"usuarios_desbloqueados": len(usuarios)},
        descripcion=f"Superadmin reactivó el estado de {len(usuarios)} cuenta(s) en la clínica {clinica.nombre_comercial}",
    )
    db.commit()

    return DesbloquearResponse(
        mensaje=f"Se han reactivado y desbloqueado {len(usuarios)} cuenta(s) de la clínica.",
        total_desbloqueados=len(usuarios),
    )


@router.put("/clinicas/{id_clinica}/excepciones", response_model=ClinicaExcepcionesOut)
def actualizar_excepciones_clinica(
    id_clinica: int,
    payload: ClinicaExcepcionesUpdate,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    antiguos = {
        "limite_pacientes_extra": getattr(clinica, "limite_pacientes_extra", 0),
        "limite_personal_extra": getattr(clinica, "limite_personal_extra", 0),
        "dias_gracia": getattr(clinica, "dias_gracia", 0),
        "fecha_fin_gracia": str(clinica.fecha_fin_gracia) if clinica.fecha_fin_gracia else None,
        "motivo_excepcion": clinica.motivo_excepcion,
    }

    clinica.limite_pacientes_extra = max(0, payload.limite_pacientes_extra)
    clinica.limite_personal_extra = max(0, payload.limite_personal_extra)
    clinica.dias_gracia = max(0, payload.dias_gracia)
    clinica.fecha_fin_gracia = payload.fecha_fin_gracia
    clinica.motivo_excepcion = payload.motivo_excepcion

    nuevos = {
        "limite_pacientes_extra": clinica.limite_pacientes_extra,
        "limite_personal_extra": clinica.limite_personal_extra,
        "dias_gracia": clinica.dias_gracia,
        "fecha_fin_gracia": str(clinica.fecha_fin_gracia) if clinica.fecha_fin_gracia else None,
        "motivo_excepcion": clinica.motivo_excepcion,
    }

    registrar_auditoria(
        db,
        superadmin,
        "ACTUALIZAR_EXCEPCIONES_CUOTA",
        "clinicas",
        id_clinica,
        antiguos,
        nuevos,
        descripcion=f"Superadmin configuró excepciones para {clinica.nombre_comercial}: +{clinica.limite_pacientes_extra} pac, +{clinica.limite_personal_extra} staff",
    )
    db.commit()

    return ClinicaExcepcionesOut(
        limite_pacientes_extra=clinica.limite_pacientes_extra,
        limite_personal_extra=clinica.limite_personal_extra,
        dias_gracia=clinica.dias_gracia,
        fecha_fin_gracia=clinica.fecha_fin_gracia,
        motivo_excepcion=clinica.motivo_excepcion,
    )


@router.get("/clinicas/{id_clinica}/auditoria", response_model=AuditoriaPaginadaOut)
def listar_auditoria_clinica(
    id_clinica: int,
    page: int = 1,
    page_size: int = 20,
    accion: str | None = None,
    nombre_tabla: str | None = None,
    buscar: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(RegistroAuditoria)
        .join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK)
        .filter(Usuario.clinica_id_FK == id_clinica)
    )

    if accion:
        query = query.filter(RegistroAuditoria.accion.ilike(f"%{accion}%"))
    if nombre_tabla:
        query = query.filter(RegistroAuditoria.nombre_tabla.ilike(f"%{nombre_tabla}%"))
    if desde:
        query = query.filter(RegistroAuditoria.marca_tiempo >= desde)
    if hasta:
        query = query.filter(RegistroAuditoria.marca_tiempo <= hasta)
    if buscar:
        termino = f"%{buscar}%"
        query = query.filter(
            (RegistroAuditoria.descripcion.ilike(termino))
            | (RegistroAuditoria.accion.ilike(termino))
            | (Usuario.nombre.ilike(termino))
            | (Usuario.correo_electronico.ilike(termino))
            | (RegistroAuditoria.direccion_ip.ilike(termino))
        )

    total = query.count()
    offset = max(0, (page - 1) * page_size)
    registros = (
        query.options(joinedload(RegistroAuditoria.usuario).joinedload(Usuario.rol))
        .order_by(RegistroAuditoria.marca_tiempo.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_consultas = (
        db.query(RegistroAuditoria)
        .join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK)
        .filter(Usuario.clinica_id_FK == id_clinica, RegistroAuditoria.accion.ilike("%CONSULTAR%"))
        .count()
    )
    total_modificaciones = (
        db.query(RegistroAuditoria)
        .join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK)
        .filter(
            Usuario.clinica_id_FK == id_clinica,
            ~RegistroAuditoria.accion.ilike("%CONSULTAR%"),
            ~RegistroAuditoria.accion.ilike("%LOGIN%"),
        )
        .count()
    )
    usuarios_activos_conteo = (
        db.query(func.count(func.distinct(RegistroAuditoria.usuario_id_FK)))
        .join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK)
        .filter(Usuario.clinica_id_FK == id_clinica)
        .scalar()
        or 0
    )

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    data = [
        AuditoriaRegistroDetalleOut(
            id=r.id_PK,
            usuario_id=r.usuario_id_FK,
            usuario_nombre=f"{r.usuario.nombre} {r.usuario.apellido_paterno or ''}".strip() if r.usuario else None,
            usuario_correo=r.usuario.correo_electronico if r.usuario else None,
            usuario_rol=r.usuario.rol.nombre if r.usuario and r.usuario.rol else "Usuario",
            accion=r.accion or "ACCION",
            nombre_tabla=r.nombre_tabla,
            id_registro=r.id_registro,
            descripcion=r.descripcion,
            valores_antiguos=r.valores_antiguos,
            valores_nuevos=r.valores_nuevos,
            direccion_ip=r.direccion_ip,
            marca_tiempo=r.marca_tiempo,
        )
        for r in registros
    ]

    return AuditoriaPaginadaOut(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        resumen=ResumenAuditoriaOut(
            total_eventos=total,
            total_consultas=total_consultas,
            total_modificaciones=total_modificaciones,
            usuarios_activos_conteo=int(usuarios_activos_conteo),
        ),
    )


@router.get("/clinicas/{id_clinica}/exportar")
def exportar_datos_clinica(
    id_clinica: int,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    from app.models.sala import Sala
    from app.models.medicamento import Medicamento

    usuarios = db.query(Usuario).filter(Usuario.clinica_id_FK == id_clinica).all()
    pacientes = db.query(Paciente).filter(Paciente.clinica_id_FK == id_clinica).all()
    citas = db.query(Cita).filter(Cita.clinica_id_FK == id_clinica).all()
    salas = db.query(Sala).filter(Sala.clinica_id_FK == id_clinica).all()
    medicamentos = db.query(Medicamento).filter(Medicamento.clinica_id_FK == id_clinica).all()

    export_data = {
        "export_metadata": {
            "plataforma": "VITALIA API",
            "version": "1.0",
            "generado_por_superadmin_id": superadmin.id_PK,
            "fecha_exportacion": datetime.now().isoformat(),
        },
        "clinica": {
            "id": clinica.id_PK,
            "nombre_comercial": clinica.nombre_comercial,
            "fecha_registro": clinica.fecha_registro.isoformat() if clinica.fecha_registro else None,
            "activa": clinica.activa,
            "plan": clinica.plan.nombre if clinica.plan else None,
            "paypal_subscription_id": clinica.paypal_subscription_id,
        },
        "usuarios": [
            {
                "id": u.id_PK,
                "nombre": u.nombre,
                "apellido_paterno": u.apellido_paterno,
                "correo": u.correo_electronico,
                "rol": u.rol.nombre if u.rol else None,
                "estado": u.estado,
                "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            }
            for u in usuarios
        ],
        "pacientes": [
            {
                "id": p.id_PK,
                "nombre": p.nombre,
                "apellido_paterno": p.apellido_paterno,
                "apellido_materno": p.apellido_materno,
                "curp": getattr(p, "curp", None),
                "telefono": getattr(p, "telefono", None),
                "correo": getattr(p, "correo", None),
                "genero": getattr(p, "genero", None),
                "fecha_nacimiento": str(p.fecha_nacimiento) if getattr(p, "fecha_nacimiento", None) else None,
                "creado_en": p.creado_en.isoformat() if getattr(p, "creado_en", None) else None,
            }
            for p in pacientes
        ],
        "citas": [
            {
                "id": c.id_PK,
                "fecha": str(c.fecha),
                "hora_inicio": str(c.hora_inicio),
                "hora_fin": str(c.hora_fin),
                "estado": c.estado,
                "motivo": c.motivo,
                "doctor_id": c.doctor_id_FK,
                "paciente_id": c.paciente_id_FK,
                "sala_id": c.sala_id_FK,
            }
            for c in citas
        ],
        "salas": [
            {
                "id": s.id_PK,
                "nombre": s.nombre,
                "tipo": s.tipo,
                "piso": s.piso,
                "estado": s.estado,
            }
            for s in salas
        ],
        "medicamentos": [
            {
                "id": m.id_PK,
                "nombre": m.nombre,
                "principio_activo": getattr(m, "principio_activo", None),
                "presentacion": getattr(m, "presentacion", None),
                "codigo_barras": getattr(m, "codigo_barras", None),
            }
            for m in medicamentos
        ],
    }

    registrar_auditoria(
        db,
        superadmin,
        "EXPORTACION_DATOS_CLINICA",
        "clinicas",
        id_clinica,
        None,
        {"pacientes_exportados": len(pacientes), "citas_exportadas": len(citas)},
        descripcion=f"Superadmin exportó el paquete integral de datos de {clinica.nombre_comercial}",
    )
    db.commit()

    nombre_archivo = f"vitalia_backup_clinica_{id_clinica}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/clinicas/{id_clinica}/avisos", response_model=list[AvisoSuperadminOut])
def listar_avisos_clinica(
    id_clinica: int,
    db: Session = Depends(get_db),
):
    avisos = (
        db.query(AvisoSuperadmin)
        .filter((AvisoSuperadmin.clinica_id_FK == id_clinica) | (AvisoSuperadmin.clinica_id_FK.is_(None)))
        .order_by(AvisoSuperadmin.fecha_creacion.desc())
        .all()
    )
    return [
        AvisoSuperadminOut(
            id=a.id_PK,
            clinica_id=a.clinica_id_FK,
            titulo=a.titulo,
            mensaje=a.mensaje,
            tipo=a.tipo,
            activo=a.activo,
            fecha_creacion=a.fecha_creacion,
            fecha_expiracion=a.fecha_expiracion,
            creado_por_usuario_id=a.creado_por_usuario_id_FK,
        )
        for a in avisos
    ]


@router.post("/clinicas/{id_clinica}/avisos", response_model=AvisoSuperadminOut, status_code=status.HTTP_201_CREATED)
async def crear_aviso_clinica(
    id_clinica: int,
    payload: AvisoSuperadminCrear,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    clinica = db.query(Clinica).filter(Clinica.id_PK == id_clinica).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clínica no encontrada")

    nuevo_aviso = AvisoSuperadmin(
        clinica_id_FK=id_clinica,
        titulo=payload.titulo.strip(),
        mensaje=payload.mensaje.strip(),
        tipo=payload.tipo or "informativo",
        fecha_expiracion=payload.fecha_expiracion,
        creado_por_usuario_id_FK=superadmin.id_PK,
        activo=True,
    )
    db.add(nuevo_aviso)
    db.flush()

    usuarios_clinica = db.query(Usuario).filter(Usuario.clinica_id_FK == id_clinica).all()
    for u in usuarios_clinica:
        notif = Notificacion(
            usuario_id_FK=u.id_PK,
            mensaje=f"[{nuevo_aviso.titulo}] {nuevo_aviso.mensaje}",
            tipo=(nuevo_aviso.tipo or "aviso").lower(),
            enlace="/notificaciones",
            estado="no_leido",
            creado_en=datetime.now(),
        )
        db.add(notif)

    registrar_auditoria(
        db,
        superadmin,
        "CREAR_AVISO_CLINICA",
        "avisos_superadmin",
        nuevo_aviso.id_PK,
        None,
        {"clinica_id": id_clinica, "titulo": nuevo_aviso.titulo, "tipo": nuevo_aviso.tipo},
        descripcion=f"Superadmin emitió aviso a {clinica.nombre_comercial}: {nuevo_aviso.titulo}",
    )
    db.commit()
    db.refresh(nuevo_aviso)

    payload_ws = {
        "type": "aviso_superadmin",
        "title": nuevo_aviso.titulo,
        "body": nuevo_aviso.mensaje,
        "message": nuevo_aviso.mensaje,
        "tipo": nuevo_aviso.tipo,
        "clinica_id": id_clinica,
        "timestamp": datetime.now().isoformat(),
    }
    for u in usuarios_clinica:
        try:
            await manager.send_personal_message(payload_ws, f"user_{u.id_PK}")
        except Exception:
            pass

    return AvisoSuperadminOut(
        id=nuevo_aviso.id_PK,
        clinica_id=nuevo_aviso.clinica_id_FK,
        titulo=nuevo_aviso.titulo,
        mensaje=nuevo_aviso.mensaje,
        tipo=nuevo_aviso.tipo,
        activo=nuevo_aviso.activo,
        fecha_creacion=nuevo_aviso.fecha_creacion,
        fecha_expiracion=nuevo_aviso.fecha_expiracion,
        creado_por_usuario_id=nuevo_aviso.creado_por_usuario_id_FK,
    )


@router.patch("/avisos/{aviso_id}/toggle", response_model=AvisoSuperadminOut)
def toggle_aviso(
    aviso_id: int,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    aviso = db.query(AvisoSuperadmin).filter(AvisoSuperadmin.id_PK == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")

    aviso.activo = not aviso.activo
    db.commit()
    db.refresh(aviso)

    return AvisoSuperadminOut(
        id=aviso.id_PK,
        clinica_id=aviso.clinica_id_FK,
        titulo=aviso.titulo,
        mensaje=aviso.mensaje,
        tipo=aviso.tipo,
        activo=aviso.activo,
        fecha_creacion=aviso.fecha_creacion,
        fecha_expiracion=aviso.fecha_expiracion,
        creado_por_usuario_id=aviso.creado_por_usuario_id_FK,
    )


@router.delete("/avisos/{aviso_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_aviso(
    aviso_id: int,
    db: Session = Depends(get_db),
    superadmin: Usuario = Depends(exigir_superadmin),
):
    aviso = db.query(AvisoSuperadmin).filter(AvisoSuperadmin.id_PK == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")

    db.delete(aviso)
    db.commit()
