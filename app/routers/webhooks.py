"""Controlador de webhooks para recibir eventos de PayPal y gestionar el ciclo de vida del tenant."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.clinica import Clinica
from app.services.provisioning_service import aprovisionar_tenant_paypal

router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"]
)


@router.post("/paypal", status_code=status.HTTP_200_OK)
def recibir_webhook_paypal(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Procesa notificaciones de PayPal para aprovisionamiento o revocacion de acceso segun el tipo de evento."""
    event_type = payload.get("event_type")
    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campo 'event_type' no proporcionado en la notificacion"
        )

    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        resultado = aprovisionar_tenant_paypal(db=db, payload=payload)
        return {
            "status": "success",
            "event_type": event_type,
            "clinica_id": resultado.clinica.id_PK,
            "usuario_id": resultado.usuario.id_PK,
            "mensaje": "Aprovisionamiento completado exitosamente",
        }

    if event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.PAYMENT.FAILED"):
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
                detail="Identificador de suscripcion no encontrado en el payload"
            )

        clinica = db.query(Clinica).filter(
            Clinica.paypal_subscription_id == subscription_id
        ).first()

        if not clinica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clinica con suscripcion '{subscription_id}' no encontrada"
            )

        try:
            clinica.activa = False
            db.commit()
            db.refresh(clinica)
        except Exception:
            db.rollback()
            raise

        return {
            "status": "success",
            "event_type": event_type,
            "clinica_id": clinica.id_PK,
            "activa": False,
            "mensaje": "Acceso revocado para la clinica",
        }

    return {
        "status": "ignored",
        "event_type": event_type,
        "mensaje": f"Evento {event_type} recibido sin accion requerida",
    }
