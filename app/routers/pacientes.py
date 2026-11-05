from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.alergia import Alergia
from app.models.alergia_paciente import AlergiaPaciente
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.paciente import AlergiaCrear, PacienteCrear, PacienteResponse
from app.services.suscripcion_service import validar_limite_pacientes
from app.services.usuario_service import MSG_CURP_DUPLICADA, curp_ya_registrada

router = APIRouter(
    prefix="/api/pacientes",
    tags=["Pacientes"]
)


def verificar_permiso_recepcion(
    usuario_actual: Usuario
):
    if usuario_actual.rol_id_FK not in [1, 4, 5]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador, coordinador o recepcionista pueden gestionar pacientes"
        )


@router.get("/")
def obtener_pacientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    pacientes = (
        db.query(Paciente)
        .filter(Paciente.clinica_id_FK == usuario_actual.clinica_id_FK)
        .order_by(Paciente.id_PK)
        .all()
    )

    return pacientes


@router.get("/{paciente_id}", response_model=PacienteResponse)
def obtener_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    paciente = (
        db.query(Paciente)
        .filter(
            Paciente.id_PK == paciente_id,
            Paciente.clinica_id_FK == usuario_actual.clinica_id_FK
        )
        .first()
    )

    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado"
        )

    return paciente


@router.post(
    "/",
    response_model=PacienteResponse,
    status_code=status.HTTP_201_CREATED
)
def crear_paciente(
    datos: PacienteCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    verificar_permiso_recepcion(usuario_actual)

    validar_limite_pacientes(db, usuario_actual.clinica_id_FK)

    if datos.curp and curp_ya_registrada(db, datos.curp):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MSG_CURP_DUPLICADA
        )

    paciente = Paciente(
        clinica_id_FK=usuario_actual.clinica_id_FK,
        nombre=datos.nombre,
        apellido=datos.apellido,
        apellido_paterno=datos.apellido_paterno,
        apellido_materno=datos.apellido_materno,
        curp=datos.curp,
        fecha_nacimiento=datos.fecha_nacimiento,
        genero=datos.genero,
        telefono=datos.telefono,
        direccion=datos.direccion,
        correo_electronico=datos.correo_electronico,
        estado="activo"
    )

    db.add(paciente)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MSG_CURP_DUPLICADA
        )

    db.refresh(paciente)

    return paciente


@router.post("/{paciente_id}/alergias")
def agregar_alergia(
    paciente_id: int,
    datos: AlergiaCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 2, 4, 5]:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar expedientes")

    paciente = (
        db.query(Paciente)
        .filter(
            Paciente.id_PK == paciente_id,
            Paciente.clinica_id_FK == usuario_actual.clinica_id_FK
        )
        .first()
    )
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    alergia = db.query(Alergia).filter(Alergia.nombre.ilike(datos.nombre)).first()

    if not alergia:
        alergia = Alergia(
            nombre=datos.nombre,
            severidad=datos.severidad
        )
        db.add(alergia)
        db.flush()

    nueva_alergia_paciente = AlergiaPaciente(
        paciente_id_FK=paciente_id,
        alergia_id_FK=alergia.id_PK,
        severidad=datos.severidad,
        notas=datos.notas
    )

    db.add(nueva_alergia_paciente)
    db.commit()

    return {"mensaje": "Alergia agregada correctamente al expediente"}
