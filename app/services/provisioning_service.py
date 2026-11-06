"""Servicio de aprovisionamiento automatico de tenants y administradores para suscripciones de PayPal."""

from datetime import datetime
import secrets
import string
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generar_hash_password
from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion
from app.models.role import Role
from app.models.usuario import Usuario


class ResultadoAprovisionamiento:
    """Contenedor de los resultados generados durante el aprovisionamiento de un tenant."""

    def __init__(self, clinica: Clinica, usuario: Usuario, password_temporal: str) -> None:
        self.clinica = clinica
        self.usuario = usuario
        self.password_temporal = password_temporal

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def __iter__(self):
        return iter((self.clinica, self.usuario, self.password_temporal))


def generar_password_temporal(longitud: int = 14) -> str:
    """Genera una contrasena temporal segura combinando letras, digitos y caracteres especiales."""
    caracteres = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(caracteres) for _ in range(longitud))


def extraer_datos_suscripcion(payload: dict) -> tuple[str, str, str, str, str | None, str]:
    """Extrae y normaliza los datos relevantes de suscripcion, plan, suscriptor y clinica desde el payload de PayPal."""
    resource = payload.get("resource", payload) if isinstance(payload.get("resource"), dict) else payload

    subscription_id = (
        resource.get("id")
        or payload.get("id")
        or resource.get("paypal_subscription_id")
        or payload.get("paypal_subscription_id")
        or resource.get("subscription_id")
        or payload.get("subscription_id")
    )
    if not subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de suscripcion de PayPal no presente en el payload"
        )

    paypal_plan_id = (
        resource.get("plan_id")
        or payload.get("plan_id")
        or resource.get("paypal_plan_id")
        or payload.get("paypal_plan_id")
    )
    if not paypal_plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de plan de PayPal no presente en el payload"
        )

    subscriber = resource.get("subscriber", {}) if isinstance(resource.get("subscriber"), dict) else {}

    raw_email = (
        subscriber.get("email_address")
        or subscriber.get("email")
        or resource.get("email_address")
        or resource.get("email")
        or payload.get("email")
    )
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correo electronico del suscriptor no encontrado en el payload de PayPal"
        )
    email = str(raw_email).strip().lower()

    name_data = subscriber.get("name")
    first_name = ""
    last_name = None

    if isinstance(name_data, dict):
        first_name = str(name_data.get("given_name", "")).strip()
        last_name_val = name_data.get("surname")
        last_name = str(last_name_val).strip() if last_name_val else None
    elif isinstance(name_data, str) and name_data.strip():
        partes = name_data.strip().split(" ", 1)
        first_name = partes[0]
        last_name = partes[1] if len(partes) > 1 else None
    else:
        raw_name = resource.get("nombre") or payload.get("nombre") or resource.get("name") or payload.get("name")
        if isinstance(raw_name, str) and raw_name.strip():
            partes = raw_name.strip().split(" ", 1)
            first_name = partes[0]
            last_name = partes[1] if len(partes) > 1 else None

    if not first_name:
        first_name = "Administrador"

    nombre_clinica = (
        resource.get("custom_id")
        or payload.get("custom_id")
        or resource.get("nombre_comercial")
        or payload.get("nombre_comercial")
        or resource.get("clinic_name")
        or payload.get("clinic_name")
        or (f"Clínica {first_name} {last_name}".strip() if last_name else f"Clínica {first_name}")
    )

    return subscription_id, paypal_plan_id, email, first_name, last_name, nombre_clinica


def aprovisionar_tenant_paypal(db: Session, payload: dict) -> ResultadoAprovisionamiento:
    """Busca el plan, genera el tenant y crea el administrador inicial con contrasena temporal hasheada."""
    subscription_id, paypal_plan_id, email, first_name, last_name, nombre_clinica = extraer_datos_suscripcion(payload)

    try:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.paypal_plan_id == paypal_plan_id
        ).first()

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan de suscripcion con paypal_plan_id '{paypal_plan_id}' no encontrado"
            )

        clinica_existente = db.query(Clinica).filter(
            Clinica.paypal_subscription_id == subscription_id
        ).first()

        if clinica_existente:
            clinica_existente.activa = True
            clinica_existente.plan_id_FK = plan.id_PK
            usuario_admin = db.query(Usuario).filter(
                Usuario.clinica_id_FK == clinica_existente.id_PK,
                Usuario.rol_id_FK == 1
            ).first()
            db.commit()
            db.refresh(clinica_existente)
            if usuario_admin:
                db.refresh(usuario_admin)
            return ResultadoAprovisionamiento(clinica_existente, usuario_admin, "")

        clinica = Clinica(
            nombre_comercial=nombre_clinica,
            plan_id_FK=plan.id_PK,
            fecha_registro=datetime.now(),
            activa=True,
            paypal_subscription_id=subscription_id,
        )
        db.add(clinica)
        db.flush()

        password_temporal = generar_password_temporal()
        hash_password = generar_hash_password(password_temporal)

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

        usuario_existente = db.query(Usuario).filter(
            Usuario.correo_electronico == email
        ).first()

        if usuario_existente:
            usuario_existente.clinica_id_FK = clinica.id_PK
            usuario_existente.nombre = first_name
            usuario_existente.apellido_paterno = last_name
            usuario_existente.hash_contrasena = hash_password
            usuario_existente.rol_id_FK = rol_id
            usuario_existente.estado = "activo"
            usuario = usuario_existente
        else:
            usuario = Usuario(
                clinica_id_FK=clinica.id_PK,
                nombre=first_name,
                apellido_paterno=last_name,
                correo_electronico=email,
                hash_contrasena=hash_password,
                rol_id_FK=rol_id,
                estado="activo",
            )
            db.add(usuario)

        db.commit()
        db.refresh(clinica)
        db.refresh(usuario)
        return ResultadoAprovisionamiento(clinica, usuario, password_temporal)
    except Exception:
        db.rollback()
        raise
