from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.usuario import Usuario
from app.schemas.sala import SalaCreate, SalaUpdate, SalaOut, SalaEstadoUpdate
from app.schemas.equipamiento import EquipamientoCreate, EquipamientoOut
from app.schemas.common import PageResponse, PageMeta
from app.services.sala_service import SalaService

router = APIRouter(prefix="/api/salas", tags=["Salas"])


@router.get("", response_model=PageResponse[SalaOut])
def listar_salas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
    estado: Optional[str] = Query(None),
    piso: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = SalaService(db).listar(
        estado=estado, piso=piso, tipo=tipo, page=page, page_size=page_size
    )
    pages = (total + page_size - 1) // page_size
    return PageResponse[SalaOut](
        data=[SalaOut.model_validate(i) for i in items],
        meta=PageMeta(total=total, page=page, page_size=page_size, pages=pages),
    )


@router.get("/{sala_id}", response_model=SalaOut)
def obtener_sala(
    sala_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    sala = SalaService(db).obtener(sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return SalaOut.model_validate(sala)


@router.post("", response_model=SalaOut, status_code=status.HTTP_201_CREATED)
def crear_sala(
    payload: SalaCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    return SalaOut.model_validate(
        SalaService(db).crear(payload, usuario=current, request=request)
    )


@router.put("/{sala_id}", response_model=SalaOut)
def actualizar_sala(
    sala_id: int,
    payload: SalaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    sala = SalaService(db).actualizar(sala_id, payload, usuario=current, request=request)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return SalaOut.model_validate(sala)


@router.patch("/{sala_id}/estado", response_model=SalaOut)
def cambiar_estado(
    sala_id: int,
    payload: SalaEstadoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    sala = SalaService(db).cambiar_estado(
        sala_id, payload.estado, usuario=current, request=request
    )
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return SalaOut.model_validate(sala)


@router.delete("/{sala_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_sala(
    sala_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador"])),
):
    if not SalaService(db).eliminar(sala_id, usuario=current, request=request):
        raise HTTPException(status_code=404, detail="Sala no encontrada")


# ---- Equipamiento anidado ----
@router.get("/{sala_id}/equipamiento", response_model=list[EquipamientoOut])
def listar_equipamiento(
    sala_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return [
        EquipamientoOut.model_validate(e)
        for e in SalaService(db).listar_equipos(sala_id)
    ]


@router.post(
    "/{sala_id}/equipamiento",
    response_model=EquipamientoOut,
    status_code=status.HTTP_201_CREATED,
)
def agregar_equipamiento(
    sala_id: int,
    payload: EquipamientoCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    equipo = SalaService(db).agregar_equipo(
        sala_id, payload, usuario=current, request=request
    )
    if not equipo:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return EquipamientoOut.model_validate(equipo)
