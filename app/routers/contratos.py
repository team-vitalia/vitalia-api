from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.models.doctor import Doctor
from app.models.contrato_doctor import ContratoDoctor
from app.schemas.contrato_doctor import (
    ContratoCrear,
    ContratoActualizar,
    ContratoResponse,
)

router = APIRouter(
    prefix="/api/contratos",
    tags=["Contratos"],
)


def exigir_administrador(usuario: Usuario):
    if usuario.rol_id_FK != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede gestionar contratos",
        )


def obtener_doctor_usuario(db: Session, usuario: Usuario):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.usuario_id_FK == usuario.id_PK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el perfil del médico",
        )

    return doctor


def obtener_contrato_o_error(db: Session, contrato_id: int):
    contrato = (
        db.query(ContratoDoctor)
        .filter(ContratoDoctor.id_PK == contrato_id)
        .first()
    )

    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el contrato",
        )

    return contrato


def validar_vigencia(fecha_inicio, fecha_fin):
    if fecha_inicio is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de inicio es obligatoria",
        )

    if fecha_fin is not None and fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de fin no puede ser anterior a la fecha de inicio",
        )


# CONSULTAR CONTRATOS
@router.get(
    "/",
    response_model=list[ContratoResponse],
)
def listar_contratos(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    if usuario_actual.rol_id_FK == 1:
        return (
            db.query(ContratoDoctor)
            .order_by(ContratoDoctor.id_PK.desc())
            .all()
        )

    if usuario_actual.rol_id_FK == 2:
        doctor = obtener_doctor_usuario(db, usuario_actual)

        return (
            db.query(ContratoDoctor)
            .filter(ContratoDoctor.doctor_id_FK == doctor.id_PK)
            .order_by(ContratoDoctor.id_PK.desc())
            .all()
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para consultar contratos",
    )
    

# CONSULTAR MI CONTRATO (MÉDICO)
@router.get(
    "/mi-contrato",
    response_model=list[ContratoResponse],
)
def consultar_mi_contrato(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    # Solo los médicos pueden consultar esta ruta.
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los médicos pueden consultar sus contratos",
        )
    
    # Obtener el perfil del médico autenticado.
    doctor = obtener_doctor_usuario(db, usuario_actual)

    print("Usuario autenticado:", usuario_actual.id_PK)
    print("Rol autenticado:", usuario_actual.rol_id_FK)
    print("Perfil del médico:", doctor.id_PK)
    print("Usuario asociado al médico:", doctor.usuario_id_FK)

    # Consultar todos los contratos para diagnóstico.
    todos = (
        db.query(ContratoDoctor)
        .order_by(ContratoDoctor.id_PK.desc())
        .all()
    )

    print(
        "Todos los contratos visibles desde la API:",
        [
            {
                "contrato_id": c.id_PK,
                "doctor_id": c.doctor_id_FK,
                "estado": c.estado,
            }
            for c in todos
        ],
    )

    # Consultar los contratos del médico autenticado.
    contratos = (
        db.query(ContratoDoctor)
        .filter(
            ContratoDoctor.doctor_id_FK == doctor.id_PK
        )
        .order_by(ContratoDoctor.id_PK.desc())
        .all()
    )

    print(
        "Contratos del médico autenticado:",
        [
            {
                "contrato_id": c.id_PK,
                "doctor_id": c.doctor_id_FK,
            }
            for c in contratos
        ],
    )

    return contratos


# CONSULTAR UN CONTRATO
@router.get(
    "/{contrato_id}",
    response_model=ContratoResponse,
)
def consultar_contrato(
    contrato_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    contrato = obtener_contrato_o_error(db, contrato_id)

    if usuario_actual.rol_id_FK == 1:
        return contrato

    if usuario_actual.rol_id_FK == 2:
        doctor = obtener_doctor_usuario(db, usuario_actual)

        if contrato.doctor_id_FK != doctor.id_PK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes consultar contratos de otros médicos",
            )

        return contrato

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para consultar este contrato",
    )
    
# REGISTRAR CONTRATO
@router.post(
    "/",
    response_model=ContratoResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_contrato(
    datos: ContratoCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_administrador(usuario_actual)

    doctor = (
        db.query(Doctor)
        .filter(Doctor.id_PK == datos.doctor_id_FK)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El médico seleccionado no existe",
        )

    validar_vigencia(datos.fecha_inicio, datos.fecha_fin)

    contrato = ContratoDoctor(
        doctor_id_FK=datos.doctor_id_FK,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        estado=datos.estado.strip(),
        tipo_contrato=datos.tipo_contrato.strip(),
        salario=datos.salario,
        url_documento=None,
    )

    try:
        db.add(contrato)
        db.commit()
        db.refresh(contrato)
        return contrato

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el contrato",
        )
        

# ACTUALIZAR CONTRATO
@router.put(
    "/{contrato_id}",
    response_model=ContratoResponse,
)
def actualizar_contrato(
    contrato_id: int,
    datos: ContratoActualizar,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    # Solo el administrador puede actualizar contratos.
    exigir_administrador(usuario_actual)

    # Buscar el contrato que se desea modificar.
    contrato = obtener_contrato_o_error(db, contrato_id)

    # Obtener únicamente los campos enviados en la solicitud.
    cambios = datos.model_dump(
        exclude_unset=True,
        exclude={"url_documento"},
    )

    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar al menos un campo para actualizar",
        )

    # Validar las fechas nuevas junto con las que ya existen.
    fecha_inicio = cambios.get(
        "fecha_inicio",
        contrato.fecha_inicio,
    )

    fecha_fin = cambios.get(
        "fecha_fin",
        contrato.fecha_fin,
    )

    validar_vigencia(fecha_inicio, fecha_fin)

    # Validar el médico solamente si se envió ese campo.
    if "doctor_id_FK" in cambios:
        doctor_id = cambios["doctor_id_FK"]

        doctor = (
            db.query(Doctor)
            .filter(Doctor.id_PK == doctor_id)
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El médico seleccionado no existe",
            )

    # Aplicar TODOS los cambios antes de guardar.
    for campo, valor in cambios.items():
        if campo in ("estado", "tipo_contrato") and valor is not None:
            valor = valor.strip()

        setattr(contrato, campo, valor)

    # Guardar una sola vez después de modificar todos los campos.
    try:
        db.commit()
        db.refresh(contrato)
        return contrato

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el contrato",
        )