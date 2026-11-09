import os
from dotenv import load_dotenv

load_dotenv()


_SECRET_POR_DEFECTO = "clave-secreta-por-defecto"
_ENTORNO = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
_SECRET = os.getenv("SECRET_KEY", _SECRET_POR_DEFECTO)

# En producción NO se permite arrancar con la clave por defecto (cualquiera podría
# firmar tokens válidos). Define SECRET_KEY y APP_ENV=production en el entorno.
if _ENTORNO in ("production", "prod") and _SECRET in (_SECRET_POR_DEFECTO, "clave-temporal-vitalia", ""):
    raise RuntimeError("SECRET_KEY no configurada: define una clave larga y aleatoria en producción")


class Settings:
    SECRET_KEY: str = _SECRET

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")
    )
    FRONTEND_RESET_URL: str = os.getenv(
        "FRONTEND_RESET_URL",
        "http://192.168.100.14:8081/recuperar"
    )
    GROQ_API_KEY: str = os.getenv(
        "GROQ_API_KEY",
        ""
    )
    GROQ_MODEL: str = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b"
    )


settings = Settings()
