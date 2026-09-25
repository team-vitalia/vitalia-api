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

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


settings = Settings()