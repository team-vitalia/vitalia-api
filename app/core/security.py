from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def verificar_password(
    password: str,
    password_hash: str
) -> bool:
    return pwd_context.verify(
        password,
        password_hash
    )


def generar_hash_password(
    password: str
) -> str:
    return pwd_context.hash(password)


def crear_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    clinica_id: int | None = None
) -> str:
    to_encode = data.copy()

    if clinica_id is not None:
        to_encode["clinica_id"] = clinica_id
    elif "clinica_id" not in to_encode and "clinica_id_FK" in to_encode:
        to_encode["clinica_id"] = to_encode["clinica_id_FK"]

    if expires_delta:
        expire = (
            datetime.now(timezone.utc)
            + expires_delta
        )
    else:
        expire = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )

    to_encode.update({
        "exp": expire
    })

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
