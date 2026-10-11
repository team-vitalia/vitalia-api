import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Permitir OAuth sobre HTTP en entornos de desarrollo local y permitir variación de scopes devueltos por Google
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

logger = logging.getLogger("vitalia.calendar_service")
logging.basicConfig(level=logging.INFO)

# Alcances (scopes) necesarios para Google Calendar y autenticación de usuario
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
]

# Rutas absolutas seguras a los archivos en la carpeta Api
API_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDENTIALS_STORAGE_FILE = os.path.join(API_DIR, "credentials.json")
TOKENS_STORAGE_FILE = os.path.join(API_DIR, "tokens.json")


class GoogleCalendarService:
    def __init__(self):
        # <TU_CLIENT_ID_AQUI> y secret pueden configurarse vía credentials.json o variables de entorno
        self.credentials_path = os.getenv("GOOGLE_CREDENTIALS_FILE", CREDENTIALS_STORAGE_FILE)
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "<TU_CLIENT_ID_AQUI>")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "<TU_CLIENT_SECRET_AQUI>")
        self._load_client_secrets_if_available()
        self.tokens_cache: Dict[str, Dict[str, Any]] = self._load_persisted_tokens()

    def _load_client_secrets_if_available(self) -> None:
        """Carga automáticamente el client_id y client_secret desde credentials.json si existen."""
        if self.has_credentials_file():
            try:
                with open(self.credentials_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    web_or_installed = data.get("web") or data.get("installed") or {}
                    if web_or_installed.get("client_id"):
                        self.client_id = web_or_installed["client_id"]
                    if web_or_installed.get("client_secret"):
                        self.client_secret = web_or_installed["client_secret"]
                    logger.info("Credenciales del cliente cargadas exitosamente desde credentials.json.")
            except Exception as e:
                logger.error(f"Error al leer client_id y client_secret desde {self.credentials_path}: {e}")

    def _load_persisted_tokens(self) -> Dict[str, Dict[str, Any]]:
        """Carga los tokens guardados en disco de forma segura y permanente."""
        if os.path.exists(TOKENS_STORAGE_FILE):
            try:
                with open(TOKENS_STORAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Cargadas credenciales persistentes de {len(data)} usuarios desde tokens.json.")
                    return data
            except Exception as e:
                logger.error(f"Error al leer tokens persistentes desde {TOKENS_STORAGE_FILE}: {e}")
        return {}

    def _save_persisted_tokens(self) -> None:
        """Guarda en disco de forma permanente las credenciales."""
        try:
            with open(TOKENS_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tokens_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error al guardar tokens en {TOKENS_STORAGE_FILE}: {e}")

    def save_user_credentials(
        self,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expiry: Optional[str] = None
    ) -> None:
        """Guarda y persiste de forma permanente las credenciales de un usuario."""
        existing = self.tokens_cache.get(user_id, {})
        # Si no llega un nuevo refresh_token, conservar el refresh_token previo
        final_refresh_token = refresh_token or existing.get("refresh_token")

        self.tokens_cache[user_id] = {
            "access_token": access_token,
            "refresh_token": final_refresh_token,
            "expiry": expiry or existing.get("expiry"),
            "updated_at": datetime.now().isoformat()
        }
        self._save_persisted_tokens()
        logger.info(f"Credenciales de Google guardadas permanentemente para usuario '{user_id}'. Tiene refresh_token: {bool(final_refresh_token)}")

    def get_user_credentials(self, user_id: str) -> Optional[Credentials]:
        """
        Recupera las credenciales del usuario y si el token de acceso expiró,
        lo renueva automáticamente con Google usando el refresh_token de forma autónoma.
        """
        user_data = self.tokens_cache.get(user_id)
        if not user_data:
            return None

        creds = Credentials(
            token=user_data.get("access_token"),
            refresh_token=user_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id if self.client_id != "<TU_CLIENT_ID_AQUI>" else None,
            client_secret=self.client_secret if self.client_secret != "<TU_CLIENT_SECRET_AQUI>" else None,
            scopes=SCOPES
        )

        # Si el token ha expirado y se cuenta con refresh_token, renovarlo automáticamente
        if creds.expired and creds.refresh_token:
            try:
                logger.info(f"Renovando token de acceso expirado para usuario '{user_id}'...")
                creds.refresh(Request())
                self.save_user_credentials(
                    user_id=user_id,
                    access_token=creds.token,
                    refresh_token=creds.refresh_token,
                    expiry=creds.expiry.isoformat() if creds.expiry else None
                )
                logger.info(f"Token renovado exitosamente para '{user_id}'.")
            except Exception as e:
                logger.error(f"No se pudo autorenovar el token para '{user_id}': {e}")

        return creds

    def is_user_connected(self, user_id: str) -> bool:
        """Indica si el usuario tiene una sesión de Google Calendar activa y disponible en el servidor."""
        creds = self.get_user_credentials(user_id)
        return bool(creds and (creds.valid or creds.refresh_token))

    def disconnect_user(self, user_id: str) -> bool:
        """Desvincula permanentemente las credenciales de un usuario."""
        if user_id in self.tokens_cache:
            del self.tokens_cache[user_id]
            self._save_persisted_tokens()
            logger.info(f"Credenciales de Google desvinculadas para usuario '{user_id}'.")
            return True
        return False

    def has_credentials_file(self) -> bool:
        """Verifica de manera segura si existe el archivo credentials.json."""
        return os.path.exists(self.credentials_path)

    def exchange_code_for_credentials(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> Credentials:
        """Intercambia un código de autorización por tokens con Google."""
        logger.info(f"Intercambiando código con Google. redirect_uri={redirect_uri}, tiene code_verifier={bool(code_verifier)}")
        if self.has_credentials_file():
            flow = Flow.from_client_secrets_file(
                self.credentials_path,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
        else:
            client_config = {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )

        fetch_kwargs = {"code": code}
        if code_verifier:
            fetch_kwargs["code_verifier"] = code_verifier

        try:
            flow.fetch_token(**fetch_kwargs)
            logger.info("Tokens de Google obtenidos y validados exitosamente!")
            return flow.credentials
        except Exception as e:
            logger.error(f"Fallo al canjear código con Google: {e}", exc_info=True)
            raise e

    def build_credentials_from_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> Credentials:
        """Construye Credentials a partir de tokens."""
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id if self.client_id != "<TU_CLIENT_ID_AQUI>" else None,
            client_secret=self.client_secret if self.client_secret != "<TU_CLIENT_SECRET_AQUI>" else None,
            scopes=SCOPES
        )

    def get_calendar_client(self, credentials: Credentials):
        """Crea y retorna el cliente oficial de Google Calendar v3."""
        return build("calendar", "v3", credentials=credentials)

    def create_test_event(
        self,
        credentials: Credentials,
        summary: str = "Cita Médica VITALIA - Prueba",
        description: str = "Cita médica agendada desde el sistema integral VITALIA.",
        start_time: Optional[datetime] = None,
        duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """Crea un evento en el calendario principal del usuario."""
        service = self.get_calendar_client(credentials)

        if not start_time:
            now = datetime.now()
            tomorrow = now + timedelta(days=1)
            start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

        end_time = start_time + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "America/Mexico_City"
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "America/Mexico_City"
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 60}
                ]
            }
        }

        try:
            created_event = service.events().insert(
                calendarId="primary",
                body=event_body
            ).execute()
            logger.info(f"Evento creado exitosamente en Google Calendar con ID: {created_event.get('id')}")
            return created_event
        except HttpError as error:
            logger.error(f"Error de Google Calendar al crear evento: {error}")
            raise error

    def delete_event(self, credentials: Credentials, event_id: str) -> bool:
        """Elimina un evento de Google Calendar dado su ID."""
        service = self.get_calendar_client(credentials)
        try:
            service.events().delete(
                calendarId="primary",
                eventId=event_id
            ).execute()
            logger.info(f"Evento {event_id} eliminado exitosamente de Google Calendar.")
            return True
        except HttpError as error:
            logger.error(f"Error al eliminar evento {event_id}: {error}")
            raise error


calendar_service = GoogleCalendarService()
