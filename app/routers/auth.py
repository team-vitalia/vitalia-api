from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import crear_access_token, generar_hash_password
from app.database.connection import get_db
from app.models.clinica import Clinica
from app.models.usuario import Usuario
from app.schemas.auth import GoogleLoginRequest, LoginRequest, TokenResponse
from app.schemas.usuario import PacienteRegistro, UsuarioCrear
from app.services.auth_service import (
    MENSAJE_CLINICA_SUSPENDIDA,
    MENSAJE_CUENTA_DESACTIVADA,
    ClinicaSuspendida,
    CuentaDesactivada,
    autenticar_usuario,
    es_superadmin_plataforma,
)
from app.services.google_auth_service import verificar_token_google
from app.services.usuario_service import ROL_PACIENTE, crear_usuario_con_perfil

router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    datos: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        resultado = autenticar_usuario(
            db=db,
            correo_electronico=datos.correo_electronico,
            password=datos.password,
        )
    except CuentaDesactivada:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MENSAJE_CUENTA_DESACTIVADA,
        )
    except ClinicaSuspendida:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MENSAJE_CLINICA_SUSPENDIDA,
        )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    return {
        "access_token": resultado["access_token"],
        "token_type": "bearer",
    }


@router.post(
    "/google-login",
    response_model=TokenResponse,
)
@router.post(
    "/google",
    response_model=TokenResponse,
)
def login_google(
    datos: GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    token_str = datos.token or datos.id_token or datos.access_token
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el token de Google para autenticar",
        )

    try:
        payload = verificar_token_google(token_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    correo = payload.get("email", "").strip().lower()
    if not correo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de Google no contiene un correo electrónico válido",
        )

    usuario = (
        db.query(Usuario)
        .options(
            joinedload(Usuario.clinica),
            joinedload(Usuario.rol),
        )
        .filter(Usuario.correo_electronico == correo)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe una cuenta registrada con este correo de Google. Por favor, registra tu clínica primero.",
        )

    if usuario.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MENSAJE_CUENTA_DESACTIVADA,
        )

    clinica = usuario.clinica or (
        db.query(Clinica).filter(Clinica.id_PK == usuario.clinica_id_FK).first()
        if usuario.clinica_id_FK
        else None
    )

    if clinica is not None and not clinica.activa:
        if not es_superadmin_plataforma(usuario):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=MENSAJE_CLINICA_SUSPENDIDA,
            )

    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = datetime.now()
    if not usuario.auth_provider:
        usuario.auth_provider = "google"

    db.commit()
    db.refresh(usuario)

    access_token = crear_access_token(
        data={
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK,
            "clinica_id": usuario.clinica_id_FK,
        },
        clinica_id=usuario.clinica_id_FK,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/google-verify",
)
def verificar_google(
    datos: GoogleLoginRequest,
):
    token_str = datos.token or datos.id_token or datos.access_token
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el token de Google",
        )

    try:
        payload = verificar_token_google(token_str)
        return {
            "email": payload.get("email"),
            "name": payload.get("name"),
            "sub": payload.get("sub"),
            "picture": payload.get("picture"),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(
    "/registro",
    status_code=status.HTTP_201_CREATED,
)
def registrar_paciente(
    datos: PacienteRegistro,
    db: Session = Depends(get_db),
):
    usuario = crear_usuario_con_perfil(
        db=db,
        datos=UsuarioCrear(
            **datos.model_dump(),
            rol_id_FK=ROL_PACIENTE,
        ),
        hash_contrasena=generar_hash_password(datos.password),
    )

    return {
        "mensaje": "Cuenta creada correctamente. Ya puedes iniciar sesión.",
        "usuario": {
            "id_PK": usuario.id_PK,
            "nombre": usuario.nombre,
            "apellido_paterno": usuario.apellido_paterno,
            "apellido_materno": usuario.apellido_materno,
            "correo_electronico": usuario.correo_electronico,
        },
    }
