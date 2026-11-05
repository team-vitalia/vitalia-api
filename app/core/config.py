import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "clave-secreta-por-defecto"
    )

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
