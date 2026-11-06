"""Controlador para el flujo de pre-registro y suscripciones SaaS de VITALIA."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generar_hash_password
from app.database.connection import get_db
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario
from app.schemas.suscripcion import PreRegistroRequest, PreRegistroResponse

router = APIRouter(
    prefix="/api/suscripciones",
    tags=["Suscripciones"]
)


@router.post(
    "/pre-registro",
    response_model=PreRegistroResponse,
    status_code=status.HTTP_201_CREATED
)
def preregistro_clinica(
    datos: PreRegistroRequest,
    db: Session = Depends(get_db)
):
    """Guarda temporalmente los datos de la clinica y administrador en estado inactivo antes del pago en PayPal."""
    nombre_clinica = datos.nombre_clinica.strip()
    nombre_admin = datos.nombre_admin.strip()
    correo = datos.correo.strip().lower()
    paypal_plan_id = datos.paypal_plan_id.strip()

    if not nombre_clinica or not nombre_admin or not correo or not datos.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Todos los campos son obligatorios"
        )

    try:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.paypal_plan_id == paypal_plan_id
        ).first()

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan de suscripción con paypal_plan_id '{paypal_plan_id}' no encontrado"
            )

        usuario_existente = db.query(Usuario).filter(
            Usuario.correo_electronico == correo
        ).first()

        if usuario_existente:
            if usuario_existente.estado == "activo" or (usuario_existente.clinica and usuario_existente.clinica.activa):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe un usuario registrado y activo con este correo electrónico"
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
                    paypal_subscription_id=None
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
                mensaje="Pre-registro actualizado exitosamente"
            )

        clinica = Clinica(
            nombre_comercial=nombre_clinica,
            plan_id_FK=plan.id_PK,
            fecha_registro=datetime.now(),
            activa=False,
            paypal_subscription_id=None
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
                esta_activo=True
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
            estado="inactivo"
        )
        db.add(usuario)

        db.commit()
        db.refresh(clinica)

        return PreRegistroResponse(
            clinica_id=clinica.id_PK,
            mensaje="Pre-registro completado exitosamente"
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
