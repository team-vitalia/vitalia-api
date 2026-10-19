from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.usuario import Usuario
from app.schemas.equipamiento import EquipamientoOut, EquipamientoUpdate
from app.services.equipamiento_service import EquipamientoService

router = APIRouter(prefix="/api/equipamiento", tags=["Equipamiento"])


@router.get("/{equipo_id}", response_model=EquipamientoOut)
def obtener_equipo(
    equipo_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    equipo = EquipamientoService(db).obtener(equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return EquipamientoOut.model_validate(equipo)


@router.put("/{equipo_id}", response_model=EquipamientoOut)
def actualizar_equipo(
    equipo_id: int,
    payload: EquipamientoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador", "Coordinador"])),
):
    equipo = EquipamientoService(db).actualizar(
        equipo_id, payload, usuario=current, request=request
    )
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return EquipamientoOut.model_validate(equipo)


@router.delete("/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_equipo(
    equipo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles(["Administrador"])),
):
    if not EquipamientoService(db).eliminar(equipo_id, usuario=current, request=request):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
