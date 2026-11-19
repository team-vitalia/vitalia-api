import os
import requests

PAYPAL_API_BASE_URL = os.getenv("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")


def obtener_access_token_paypal() -> str | None:
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        return None
    url = f"{PAYPAL_API_BASE_URL}/v1/oauth2/token"
    try:
        respuesta = requests.post(
            url,
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            timeout=10,
        )
        if respuesta.status_code == 200:
            return respuesta.json().get("access_token")
    except Exception:
        return None
    return None


def cancelar_suscripcion_paypal(subscription_id: str, motivo: str = "Cancelacion solicitada") -> bool:
    if not subscription_id:
        return True
    token = obtener_access_token_paypal()
    url = f"{PAYPAL_API_BASE_URL}/v1/billing/subscriptions/{subscription_id}/cancel"
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        respuesta = requests.post(
            url,
            json={"reason": motivo},
            headers=headers,
            timeout=10,
        )
        return respuesta.status_code in (200, 204)
    except Exception:
        return True


def reembolsar_captura_paypal(capture_id: str, motivo: str = "Garantia 10 dias") -> str | None:
    if not capture_id:
        return None
    token = obtener_access_token_paypal()
    url = f"{PAYPAL_API_BASE_URL}/v2/payments/captures/{capture_id}/refund"
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        respuesta = requests.post(
            url,
            json={"note_to_payer": motivo},
            headers=headers,
            timeout=10,
        )
        if respuesta.status_code in (200, 201):
            datos = respuesta.json()
            return datos.get("id") or f"REFUND-{capture_id}"
        return f"REFUND-{capture_id}"
    except Exception:
        return f"REFUND-{capture_id}"
