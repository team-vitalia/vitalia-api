from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.models.alergia import Alergia # 👈 NUEVO IMPORT
from app.models.alergia_paciente import AlergiaPaciente # 👈 NUEVO IMPORT
from app.schemas.paciente import PacienteCrear, PacienteResponse, AlergiaCrear # 👈 AGREGAMOS AlergiaCrear
from app.core.dependencies import get_current_user


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
        .order_by(Paciente.id_PK)
        .all()
    )

    return pacientes


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

    paciente = Paciente(
        nombre=datos.nombre,
        apellido=datos.apellido,
        fecha_nacimiento=datos.fecha_nacimiento,
        genero=datos.genero,
        telefono=datos.telefono,
        direccion=datos.direccion,
        correo_electronico=datos.correo_electronico,
        estado="activo"
    )

    db.add(paciente)
    db.commit()
    db.refresh(paciente)

    return paciente


# 👇 NUEVO ENDPOINT PARA EL CU-30 👇
@router.post("/{paciente_id}/alergias")
def agregar_alergia(
    paciente_id: int,
    datos: AlergiaCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    # Permitimos al médico (2) modificar el expediente
    if usuario_actual.rol_id_FK not in [1, 2, 4, 5]:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar expedientes")

    paciente = db.query(Paciente).filter(Paciente.id_PK == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Buscamos si la alergia ya existe en el catálogo general (tabla alergias)
    alergia = db.query(Alergia).filter(Alergia.nombre.ilike(datos.nombre)).first()
    
    # Si no existe, la creamos en el catálogo maestro
    if not alergia:
        alergia = Alergia(
            nombre=datos.nombre, 
            severidad=datos.severidad
        )
        db.add(alergia)
        db.flush() # Para obtener el ID de la nueva alergia

    # Vinculamos la alergia al paciente en la tabla intermedia
    nueva_alergia_paciente = AlergiaPaciente(
        paciente_id_FK=paciente_id,
        alergia_id_FK=alergia.id_PK,
        severidad=datos.severidad,
        notas=datos.notas
    )
    
    db.add(nueva_alergia_paciente)
    db.commit()
    
    return {"mensaje": "Alergia agregada correctamente al expediente"}