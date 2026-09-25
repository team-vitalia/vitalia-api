from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import autenticar_usuario


router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"]
)


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    datos: LoginRequest,
    db: Session = Depends(get_db)
):
    resultado = autenticar_usuario(
        db=db,
        correo_electronico=datos.correo_electronico,
        password=datos.password
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos"
        )

    return {
        "access_token": resultado["access_token"],
        "token_type": "bearer"
    }