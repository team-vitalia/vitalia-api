from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generar_hash_password, verificar_password
from app.database.connection import get_db
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.suscripcion import (
    ConfirmarSuscripcionRequest,
    ConfirmarSuscripcionResponse,
    PreRegistroRequest,
    PreRegistroResponse,
)

router = APIRouter(
    prefix="/api/suscripciones",
    tags=["Suscripciones"],
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

    if not nombre_clinica or not nombre_admin or not correo or not datos.password:
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
            usuario_existente.hash_contrasena = generar_hash_password(datos.password)
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
            hash_contrasena=generar_hash_password(datos.password),
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
def confirmar_suscripcion(
    datos: ConfirmarSuscripcionRequest,
    db: Session = Depends(get_db),
):
    clinica = None

    if datos.clinica_id:
        clinica = db.query(Clinica).filter(Clinica.id_PK == datos.clinica_id).first()

    if not clinica and datos.correo:
        user = db.query(Usuario).filter(Usuario.correo_electronico == str(datos.correo).strip().lower()).first()
        if user and user.clinica:
            clinica = user.clinica

    if not clinica and datos.subscription_id:
        clinica = db.query(Clinica).filter(Clinica.paypal_subscription_id == datos.subscription_id.strip()).first()

    if not clinica:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clínica asociada no encontrada",
        )

    clinica.activa = True
    clinica.paypal_subscription_id = datos.subscription_id.strip()

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

    return ConfirmarSuscripcionResponse(
        status="success",
        clinica_id=clinica.id_PK,
        activa=clinica.activa,
        mensaje="Suscripción activada exitosamente",
    )
