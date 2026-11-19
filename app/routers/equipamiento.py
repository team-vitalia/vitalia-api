from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.schemas.equipamiento import EquipamientoOut, EquipamientoUpdate
from app.services.equipamiento_service import EquipamientoService
from app.services.sala_service import estado_mantenimiento

router = APIRouter(prefix="/api/equipamiento", tags=["Equipamiento"])


def _servicio(db: Session, usuario: Usuario) -> EquipamientoService:
    return EquipamientoService(db, clinica_id=getattr(usuario, "clinica_id_FK", None))


def _out(equipo) -> EquipamientoOut:
    out = EquipamientoOut.model_validate(equipo)
    out.mantenimiento_estado = estado_mantenimiento(equipo)
    return out


@router.get("/{equipo_id}", response_model=EquipamientoOut)
def obtener_equipo(
    equipo_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    equipo = _servicio(db, current).obtener(equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return _out(equipo)


@router.put("/{equipo_id}", response_model=EquipamientoOut)
def actualizar_equipo(
    equipo_id: int,
    payload: EquipamientoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    equipo = _servicio(db, current).actualizar(equipo_id, payload, usuario=current, request=request)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return _out(equipo)


@router.delete("/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_equipo(
    equipo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador"])),
):
    if not _servicio(db, current).eliminar(equipo_id, usuario=current, request=request):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
