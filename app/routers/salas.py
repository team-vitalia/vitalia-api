from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.usuario import Usuario
from app.schemas.common import PageMeta, PageResponse
from app.schemas.equipamiento import EquipamientoCreate, EquipamientoOut
from app.schemas.sala import SalaCreate, SalaEstadoUpdate, SalaOut, SalaUpdate
from app.services.sala_service import SalaService, estado_mantenimiento

router = APIRouter(
    prefix="/api/salas",
    tags=["Salas"],
    dependencies=[Depends(verificar_modulo_salas)],
)

ROLES_GESTION = ["Administrador", "Coordinador"]


def _servicio(db: Session, usuario: Usuario) -> SalaService:
    return SalaService(db, clinica_id=getattr(usuario, "clinica_id_FK", None))


def _sala_out(sala, conteos=None) -> SalaOut:
    out = SalaOut.model_validate(sala)
    if isinstance(conteos, dict):
        out.total_equipos = conteos.get("total_equipos", 0)
        out.equipos_con_problema = conteos.get("equipos_con_problema", 0)
        out.citas_proximas = conteos.get("citas_proximas", 0)
    return out


def _conteo_de(servicio, sala):
    """Contadores de una sola sala (si el servicio no los puede dar, se omiten)."""
    todos = servicio.conteos([sala])
    return todos.get(sala.id_PK) if isinstance(todos, dict) else None


def _equipo_out(equipo) -> EquipamientoOut:
    out = EquipamientoOut.model_validate(equipo)
    out.mantenimiento_estado = estado_mantenimiento(equipo)
    return out


@router.get("", response_model=PageResponse[SalaOut])
def listar_salas(
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
    estado: Optional[str] = Query(None),
    piso: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    buscar: Optional[str] = Query(None, description="Texto en nombre o ubicación"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    servicio = _servicio(db, current)
    items, total = servicio.listar(
        clinica_id=getattr(current, "clinica_id_FK", None),
        estado=estado, piso=piso, tipo=tipo, buscar=buscar, page=page, page_size=page_size,
    )
    items = list(items)
    conteos = servicio.conteos(items)
    conteos = conteos if isinstance(conteos, dict) else {}
    pages = (total + page_size - 1) // page_size
    return PageResponse[SalaOut](
        data=[_sala_out(i, conteos.get(i.id_PK)) for i in items],
        meta=PageMeta(total=total, page=page, page_size=page_size, pages=pages),
    )


@router.get("/{sala_id}", response_model=SalaOut)
def obtener_sala(
    sala_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    servicio = _servicio(db, current)
    sala = servicio.obtener(sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return _sala_out(sala, _conteo_de(servicio, sala))


@router.post("", response_model=SalaOut, status_code=status.HTTP_201_CREATED)
def crear_sala(
    payload: SalaCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_GESTION)),
):
    return _sala_out(_servicio(db, current).crear(payload, usuario=current, request=request))


@router.put("/{sala_id}", response_model=SalaOut)
def actualizar_sala(
    sala_id: int,
    payload: SalaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_GESTION)),
):
    servicio = _servicio(db, current)
    sala = servicio.actualizar(sala_id, payload, usuario=current, request=request)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return _sala_out(sala, _conteo_de(servicio, sala))


@router.patch("/{sala_id}/estado", response_model=SalaOut)
def cambiar_estado(
    sala_id: int,
    payload: SalaEstadoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(ROLES_GESTION)),
):
    servicio = _servicio(db, current)
    sala = servicio.cambiar_estado(sala_id, payload.estado, usuario=current, request=request)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return _sala_out(sala, _conteo_de(servicio, sala))


@router.delete("/{sala_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_sala(
    sala_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador"])),
):
    if not _servicio(db, current).eliminar(sala_id, usuario=current, request=request):
        raise HTTPException(status_code=404, detail="Sala no encontrada")


# ---- Equipamiento anidado ----
@router.get("/{sala_id}/equipamiento", response_model=list[EquipamientoOut])
def listar_equipamiento(
    sala_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    equipos = _servicio(db, current).listar_equipos(sala_id)
    if equipos is None:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return [_equipo_out(e) for e in equipos]


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
    current: Usuario = Depends(require_roles(ROLES_GESTION)),
):
    equipo = _servicio(db, current).agregar_equipo(sala_id, payload, usuario=current, request=request)
    if not equipo:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return _equipo_out(equipo)
