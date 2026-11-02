from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generar_hash_password
from app.database.connection import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.usuario import PacienteRegistro, UsuarioCrear
from app.services.auth_service import autenticar_usuario
from app.services.usuario_service import ROL_PACIENTE, crear_usuario_con_perfil


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


@router.post(
    "/registro",
    status_code=status.HTTP_201_CREATED
)
def registrar_paciente(
    datos: PacienteRegistro,
    db: Session = Depends(get_db)
):
    """
    Registro PÚBLICO (sin sesión) exclusivo para pacientes.

    Seguridad: el rol NO se lee de la solicitud. `PacienteRegistro` no tiene
    campo de rol y rechaza (422) cualquier campo adicional; aquí el servidor
    fija el rol Paciente. Así ninguna llamada directa a la API puede crear
    administradores, doctores, recepcionistas ni coordinadores.
    """

    usuario = crear_usuario_con_perfil(
        db=db,
        datos=UsuarioCrear(
            **datos.model_dump(),
            rol_id_FK=ROL_PACIENTE
        ),
        hash_contrasena=generar_hash_password(datos.password)
    )

    return {
        "mensaje": "Cuenta creada correctamente. Ya puedes iniciar sesión.",
        "usuario": {
            "id_PK": usuario.id_PK,
            "nombre": usuario.nombre,
            "apellido_paterno": usuario.apellido_paterno,
            "apellido_materno": usuario.apellido_materno,
            "correo_electronico": usuario.correo_electronico
        }
    }
