import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = "VITALIA API"
    APP_VERSION: str = "1.0.0"

    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "clave-temporal-vitalia"
    )

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")
    )
    FRONTEND_RESET_URL: str = os.getenv(
        "FRONTEND_RESET_URL",
        "http://192.168.100.14:8081/recuperar"
    )


settings = Settings()