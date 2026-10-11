from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.models.doctor import Doctor
from app.models.contrato_doctor import ContratoDoctor
from app.services.contrato_pdf import generar_pdf_contrato
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
        # 1. Crear el registro para obtener su ID.
        db.add(contrato)
        db.flush()

        # 2. Generar el PDF en la carpeta del médico.
        ruta_pdf = generar_pdf_contrato(contrato, doctor)

        # 3. Guardar la ruta del archivo en MySQL.
        contrato.url_documento = ruta_pdf

        # 4. Confirmar el registro.
        db.commit()
        db.refresh(contrato)

        return contrato

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el contrato ni generar su PDF",
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
    exigir_administrador(usuario_actual)

    contrato = obtener_contrato_o_error(db, contrato_id)

    # El administrador no debe modificar manualmente la ruta del PDF.
    cambios = datos.model_dump(
        exclude_unset=True,
        exclude={"url_documento"},
    )

    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar al menos un campo para actualizar",
        )

    fecha_inicio = cambios.get(
        "fecha_inicio",
        contrato.fecha_inicio,
    )
    fecha_fin = cambios.get(
        "fecha_fin",
        contrato.fecha_fin,
    )

    validar_vigencia(fecha_inicio, fecha_fin)

    # Si se cambia el médico, comprobar que exista.
    doctor_id = cambios.get(
        "doctor_id_FK",
        contrato.doctor_id_FK,
    )

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

    for campo, valor in cambios.items():
        if campo in ("estado", "tipo_contrato") and valor is not None:
            valor = valor.strip()

        setattr(contrato, campo, valor)

    try:
        # Aplicar los cambios antes de generar el documento.
        db.flush()

        # Crear nuevamente el PDF con los datos actualizados.
        ruta_pdf = generar_pdf_contrato(contrato, doctor)
        contrato.url_documento = ruta_pdf

        db.commit()
        db.refresh(contrato)

        return contrato

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el contrato ni regenerar su PDF",
        )