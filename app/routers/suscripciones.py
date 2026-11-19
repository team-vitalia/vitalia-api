import asyncio
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import crear_access_token, generar_hash_password, verificar_password
from app.database.connection import get_db
from app.models.cancelacion_suscripcion import CancelacionSuscripcion
from app.models.clinica import Clinica
from app.models.doctor import Doctor
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.suscripcion import (
    CancelarSuscripcionRequest,
    CancelarSuscripcionResponse,
    ConfirmarSuscripcionRequest,
    ConfirmarSuscripcionResponse,
    PreRegistroRequest,
    PreRegistroResponse,
    RegistroGratuitoRequest,
    RegistroGratuitoResponse,
)
from app.services.connection_manager import manager
from app.services.paypal_service import cancelar_suscripcion_paypal, reembolsar_captura_paypal

logger = logging.getLogger("vitalia.suscripciones")

router = APIRouter(
    prefix="/api/suscripciones",
    tags=["Suscripciones"],
)


@router.post(
    "/registro-gratuito",
    response_model=RegistroGratuitoResponse,
    status_code=status.HTTP_201_CREATED,
)
def registro_gratuito(
    datos: RegistroGratuitoRequest,
    db: Session = Depends(get_db),
):
    correo = str(datos.correo).strip().lower()
    nombre_doc = (datos.nombre_doctor or datos.nombre or "").strip()
    nombre_clin = (datos.nombre_clinica or "").strip()

    if not nombre_doc and not nombre_clin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el nombre del consultorio o doctor",
        )

    if not nombre_doc:
        nombre_doc = nombre_clin
    if not nombre_clin:
        nombre_clin = f"Consultorio {nombre_doc}"

    if not datos.password or len(datos.password.strip()) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 6 caracteres",
        )

    usuario_existente = db.query(Usuario).filter(
        Usuario.correo_electronico == correo
    ).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado",
        )

    try:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.nombre == "Gratuito"
        ).first()
        if not plan:
            plan = PlanSuscripcion(
                nombre="Gratuito",
                precio_mensual=0.0,
                precio_anual=0.0,
                limite_personal=1,
                limite_pacientes=20,
                limite_pacientes_mes=20,
                incluye_calendar=False,
                incluye_correos=False,
                limite_ia_mensual=0,
                limite_sucursales=1,
                incluye_contratos=False,
                incluye_salas=False,
                incluye_almacen=False,
                incluye_reportes=False,
                incluye_auditoria=False,
                incluye_roles=False,
                paypal_plan_id=None,
            )
            db.add(plan)
            db.flush()

        clinica = Clinica(
            nombre_comercial=nombre_clin,
            plan_id_FK=plan.id_PK,
            fecha_registro=datetime.now(),
            activa=True,
            paypal_subscription_id=None,
        )
        db.add(clinica)
        db.flush()

        rol_doctor = db.query(Role).filter(Role.nombre == "Doctor").first()
        if not rol_doctor:
            rol_doctor = db.query(Role).filter(Role.id_PK == 2).first()
        if not rol_doctor:
            rol_doctor = Role(
                id_PK=2,
                nombre="Doctor",
                descripcion="Médico del sistema",
                esta_activo=True,
            )
            db.add(rol_doctor)
            db.flush()

        usuario = Usuario(
            clinica_id_FK=clinica.id_PK,
            nombre=nombre_doc,
            correo_electronico=correo,
            hash_contrasena=generar_hash_password(datos.password),
            auth_provider="manual",
            rol_id_FK=rol_doctor.id_PK,
            estado="activo",
            creado_en=datetime.now(),
        )
        db.add(usuario)
        db.flush()

        doctor_perfil = Doctor(
            usuario_id_FK=usuario.id_PK,
            estado="activo",
        )
        db.add(doctor_perfil)

        db.commit()
        db.refresh(clinica)
        db.refresh(usuario)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    token = crear_access_token(
        data={"sub": str(usuario.id_PK), "rol_id": usuario.rol_id_FK},
        clinica_id=clinica.id_PK,
    )

    return RegistroGratuitoResponse(
        status="success",
        access_token=token,
        token_type="bearer",
        clinica_id=clinica.id_PK,
        nombre_clinica=clinica.nombre_comercial,
        nombre_plan=plan.nombre,
        mensaje="Registro gratuito completado exitosamente",
        usuario_id=usuario.id_PK,
    )


@router.post(
    "/pre-registro",
    response_model=PreRegistroResponse,
    status_code=status.HTTP_201_CREATED,
)
def preregistro_clinica(
    datos: PreRegistroRequest,
    db: Session = Depends(get_db),
):
    nombre_clinica = datos.nombre_clinica.strip()
    nombre_admin = datos.nombre_admin.strip()
    correo = datos.correo.strip().lower()
    paypal_plan_id = datos.paypal_plan_id.strip()
    es_google = (datos.auth_provider == "google")

    if not nombre_clinica or not nombre_admin or not correo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Todos los campos son obligatorios",
        )

    if not es_google and not datos.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Todos los campos son obligatorios",
        )

    try:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.paypal_plan_id == paypal_plan_id
        ).first()

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan de suscripción con paypal_plan_id '{paypal_plan_id}' no encontrado",
            )

        usuario_existente = db.query(Usuario).filter(
            Usuario.correo_electronico == correo
        ).first()

        if usuario_existente:
            if usuario_existente.estado == "activo" or (usuario_existente.clinica and usuario_existente.clinica.activa):
                if not es_google:
                    if not verificar_password(datos.password, usuario_existente.hash_contrasena):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El correo ya está registrado en VITALIA. Ingresa la contraseña correcta de tu cuenta para actualizar el plan de tu clínica.",
                        )

                clinica = usuario_existente.clinica
                if clinica:
                    clinica.plan_id_FK = plan.id_PK
                    if nombre_clinica:
                        clinica.nombre_comercial = nombre_clinica
                else:
                    clinica = Clinica(
                        nombre_comercial=nombre_clinica,
                        plan_id_FK=plan.id_PK,
                        fecha_registro=datetime.now(),
                        activa=False,
                        paypal_subscription_id=None,
                    )
                    db.add(clinica)
                    db.flush()
                    usuario_existente.clinica_id_FK = clinica.id_PK

                if es_google:
                    usuario_existente.auth_provider = "google"

                db.commit()
                db.refresh(clinica)
                return PreRegistroResponse(
                    clinica_id=clinica.id_PK,
                    mensaje="Cuenta existente verificada. Procede con el pago en PayPal para confirmar tu plan.",
                )

            clinica = usuario_existente.clinica
            if clinica:
                clinica.nombre_comercial = nombre_clinica
                clinica.plan_id_FK = plan.id_PK
                clinica.activa = False
            else:
                clinica = Clinica(
                    nombre_comercial=nombre_clinica,
                    plan_id_FK=plan.id_PK,
                    fecha_registro=datetime.now(),
                    activa=False,
                    paypal_subscription_id=None,
                )
                db.add(clinica)
                db.flush()
                usuario_existente.clinica_id_FK = clinica.id_PK

            usuario_existente.nombre = nombre_admin
            if datos.password:
                usuario_existente.hash_contrasena = generar_hash_password(datos.password)
            if es_google:
                usuario_existente.auth_provider = "google"
            usuario_existente.estado = "inactivo"

            db.commit()
            db.refresh(clinica)
            return PreRegistroResponse(
                clinica_id=clinica.id_PK,
                mensaje="Pre-registro actualizado exitosamente",
            )

        clinica = Clinica(
            nombre_comercial=nombre_clinica,
            plan_id_FK=plan.id_PK,
            fecha_registro=datetime.now(),
            activa=False,
            paypal_subscription_id=None,
        )
        db.add(clinica)
        db.flush()

        rol_admin = db.query(Role).filter(Role.nombre == "Administrador").first()
        if not rol_admin:
            rol_admin = db.query(Role).first()
        if not rol_admin:
            rol_admin = Role(
                id_PK=1,
                nombre="Administrador",
                descripcion="Administrador general del sistema",
                esta_activo=True,
            )
            db.add(rol_admin)
            db.flush()
        rol_id = rol_admin.id_PK

        usuario = Usuario(
            clinica_id_FK=clinica.id_PK,
            nombre=nombre_admin,
            correo_electronico=correo,
            hash_contrasena=generar_hash_password(datos.password) if datos.password else None,
            auth_provider="google" if es_google else "manual",
            rol_id_FK=rol_id,
            estado="inactivo",
        )
        db.add(usuario)

        db.commit()
        db.refresh(clinica)

        return PreRegistroResponse(
            clinica_id=clinica.id_PK,
            mensaje="Pre-registro completado exitosamente",
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/confirmar",
    response_model=ConfirmarSuscripcionResponse,
    status_code=status.HTTP_200_OK,
)
async def confirmar_suscripcion(
    datos: ConfirmarSuscripcionRequest,
    db: Session = Depends(get_db),
):
    clinica = None
    es_upgrade = bool(datos.es_upgrade or datos.modo == "upgrade")

    if datos.clinica_id and datos.clinica_id > 0:
        clinica = db.query(Clinica).filter(Clinica.id_PK == datos.clinica_id).first()
        if clinica and clinica.activa and clinica.plan_id_FK:
            es_upgrade = True

    if not clinica and datos.correo:
        user = db.query(Usuario).filter(Usuario.correo_electronico == str(datos.correo).strip().lower()).first()
        if user and user.clinica:
            clinica = user.clinica
            if clinica.activa and clinica.plan_id_FK:
                es_upgrade = True
        elif user and not user.clinica:
            clinica = Clinica(
                nombre_comercial=datos.nombre_clinica or "Clínica VITALIA",
                plan_id_FK=1,
                activa=True,
                paypal_subscription_id=datos.subscription_id.strip(),
            )
            db.add(clinica)
            db.flush()
            user.clinica_id_FK = clinica.id_PK

    if not clinica and datos.subscription_id:
        clinica = db.query(Clinica).filter(Clinica.paypal_subscription_id == datos.subscription_id.strip()).first()

    if not clinica and datos.nombre_clinica:
        clinica = db.query(Clinica).filter(Clinica.nombre_comercial == datos.nombre_clinica.strip()).first()

    if not clinica:
        plan_id = 1
        if datos.paypal_plan_id:
            plan_obj = db.query(PlanSuscripcion).filter(
                PlanSuscripcion.paypal_plan_id == datos.paypal_plan_id.strip()
            ).first()
            if plan_obj:
                plan_id = plan_obj.id_PK

        clinica = Clinica(
            nombre_comercial=datos.nombre_clinica or "Mi Clínica",
            plan_id_FK=plan_id,
            fecha_registro=datetime.now(),
            activa=True,
            paypal_subscription_id=datos.subscription_id.strip(),
        )
        db.add(clinica)
        db.flush()

        if datos.correo:
            rol_admin = db.query(Role).filter(Role.nombre == "Administrador").first() or db.query(Role).first()
            nuevo_usuario = Usuario(
                clinica_id_FK=clinica.id_PK,
                nombre=datos.nombre_admin or "Administrador",
                correo_electronico=str(datos.correo).strip().lower(),
                hash_contrasena=generar_hash_password("Temp12345!"),
                rol_id_FK=rol_admin.id_PK if rol_admin else 1,
                estado="activo",
            )
            db.add(nuevo_usuario)

    clinica.activa = True
    clinica.paypal_subscription_id = datos.subscription_id.strip()
    clinica.fecha_inicio_suscripcion = datetime.now()

    if datos.paypal_plan_id:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.paypal_plan_id == datos.paypal_plan_id.strip()
        ).first()
        if plan:
            clinica.plan_id_FK = plan.id_PK

    admin = db.query(Usuario).filter(
        Usuario.clinica_id_FK == clinica.id_PK,
        Usuario.rol_id_FK == 1,
    ).first()

    if not admin:
        admin = db.query(Usuario).filter(
            Usuario.clinica_id_FK == clinica.id_PK
        ).first()

    if admin:
        admin.estado = "activo"

    db.commit()
    db.refresh(clinica)

    nombre_plan_actual = clinica.plan.nombre if clinica.plan else None
    precio_mensual_actual = float(clinica.plan.precio_mensual) if clinica.plan and clinica.plan.precio_mensual else 1199.0
    correo_destino = datos.correo or (admin.correo_electronico if admin else None)
    nombre_admin_efectivo = datos.nombre_admin or (admin.nombre if admin else "Administrador")
    nombre_clinica_efectivo = clinica.nombre_comercial or datos.nombre_clinica or "Clínica VITALIA"

    if correo_destino:
        try:
            from app.services.email_service import notificar_correo_confirmacion_pago
            asyncio.create_task(
                notificar_correo_confirmacion_pago(
                    destinatario=str(correo_destino).strip().lower(),
                    nombre_admin=nombre_admin_efectivo,
                    nombre_clinica=nombre_clinica_efectivo,
                    nombre_plan=nombre_plan_actual or "Clínica",
                    precio_mensual=precio_mensual_actual,
                    subscription_id=datos.subscription_id.strip(),
                    es_upgrade=es_upgrade,
                )
            )
        except Exception as e:
            logger.warning(f"Error al programar envío de correo de confirmación: {e}")

    evento_ws = {
        "type": "plan_actualizado",
        "event": "suscripcion_actualizada",
        "clinica_id": clinica.id_PK,
        "plan_id": clinica.plan_id_FK,
        "nombre_plan": nombre_plan_actual,
        "activa": clinica.activa,
        "title": "Suscripción Actualizada",
        "message": f"El plan de la clínica ha sido actualizado a {nombre_plan_actual} exitosamente.",
        "timestamp": datetime.now().isoformat(),
    }

    try:
        await manager.broadcast(evento_ws)
    except Exception as e:
        logger.warning(f"Error al emitir broadcast websocket: {e}")

    return ConfirmarSuscripcionResponse(
        status="success",
        clinica_id=clinica.id_PK,
        activa=clinica.activa,
        mensaje="Suscripción activada exitosamente",
        nombre_plan=nombre_plan_actual,
    )


@router.post(
    "/cancelar",
    response_model=CancelarSuscripcionResponse,
    status_code=status.HTTP_200_OK,
)
def cancelar_suscripcion(
    datos: CancelarSuscripcionRequest,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if not clinica_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene una clínica asociada",
        )

    clinica = db.query(Clinica).filter(Clinica.id_PK == clinica_id).first()
    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica no encontrada",
        )

    es_admin = getattr(usuario_actual, "rol_id_FK", None) == 1
    es_super = getattr(usuario_actual, "is_superadmin", False)
    es_titular = False
    if clinica:
        tiene_admin_dedicado = any(
            u.rol_id_FK == 1 for u in clinica.usuarios if u.id_PK != usuario_actual.id_PK
        )
        if not tiene_admin_dedicado:
            es_titular = True

    if not es_admin and not es_super and not es_titular:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador o titular de la clínica puede cancelar la suscripción",
        )

    if not clinica.activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La clínica no se encuentra activa",
        )

    if clinica.plan and (clinica.plan.nombre or "").strip().lower() == "gratuito":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La clínica ya se encuentra en el plan Gratuito",
        )

    subscription_id = clinica.paypal_subscription_id
    if subscription_id:
        cancelar_suscripcion_paypal(subscription_id, motivo=datos.motivo_categoria)

    fecha_inicio = clinica.fecha_inicio_suscripcion or clinica.fecha_registro or datetime.now()
    dias_transcurridos = (datetime.now() - fecha_inicio).days

    aplica_reembolso = False
    estado_reembolso = "NO_APLICA"
    paypal_refund_id = None

    if dias_transcurridos <= 10 and datos.solicitar_reembolso:
        aplica_reembolso = True
        capture_id = clinica.ultimo_pago_capture_id or f"CAP-{subscription_id or clinica.id_PK}"
        refund_id = reembolsar_captura_paypal(capture_id, motivo="Garantia 10 dias")
        if refund_id:
            estado_reembolso = "PROCESADO"
            paypal_refund_id = refund_id
        else:
            estado_reembolso = "FALLIDO"

    plan_anterior_id = clinica.plan_id_FK

    plan_gratuito = db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Gratuito"
    ).first()
    if not plan_gratuito:
        plan_gratuito = PlanSuscripcion(
            nombre="Gratuito",
            precio_mensual=0.0,
            precio_anual=0.0,
            limite_personal=1,
            limite_pacientes=20,
            limite_pacientes_mes=20,
            incluye_calendar=False,
            incluye_correos=False,
            limite_ia_mensual=0,
            limite_sucursales=1,
            incluye_contratos=False,
            incluye_salas=False,
            incluye_almacen=False,
            incluye_reportes=False,
            incluye_auditoria=False,
            incluye_roles=False,
            paypal_plan_id=None,
        )
        db.add(plan_gratuito)
        db.flush()

    try:
        clinica.plan_id_FK = plan_gratuito.id_PK
        clinica.paypal_subscription_id = None
        clinica.activa = True

        cancelacion = CancelacionSuscripcion(
            clinica_id_FK=clinica.id_PK,
            plan_anterior_id_FK=plan_anterior_id,
            fecha_cancelacion=datetime.now(),
            motivo_categoria=datos.motivo_categoria,
            comentarios_adicionales=datos.comentarios_adicionales,
            aplica_reembolso=aplica_reembolso,
            estado_reembolso=estado_reembolso,
            paypal_refund_id=paypal_refund_id,
        )
        db.add(cancelacion)
        db.commit()
        db.refresh(clinica)
        db.refresh(cancelacion)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la cancelación en base de datos",
        )

    return CancelarSuscripcionResponse(
        status="success",
        mensaje="Suscripción cancelada y cuenta migrada al Plan Gratuito exitosamente",
        clinica_id=clinica.id_PK,
        plan_actual="Gratuito",
        aplica_reembolso=aplica_reembolso,
        estado_reembolso=estado_reembolso,
        paypal_refund_id=paypal_refund_id,
        fecha_cancelacion=cancelacion.fecha_cancelacion,
    )
