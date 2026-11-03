from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user

from app.database.connection import get_db
from app.models.inventario import Inventario
from app.models.interaccion_medicamento import InteraccionMedicamento
from app.models.medicamento import Medicamento  # 👈 Importante
from app.schemas.almacen import (
    InventarioCreate,
    InventarioResponse,
    EvaluarInteraccionRequest,
    EvaluarInteraccionResponse,
    InteraccionResultado,
    MedicamentoResponse  # 👈 Importante
)

router = APIRouter(prefix="/api/almacen", tags=["Almacén e Interacciones"])


# 1. Listar el catálogo de medicamentos (CU-34 / Requerido para la App)
@router.get("/medicamentos", response_model=List[MedicamentoResponse])
def listar_medicamentos(db: Session = Depends(get_db)):
    return db.query(Medicamento).all()


# 2. Listar el inventario de almacén (CU-34 a CU-38)
@router.get("/inventario", response_model=List[InventarioResponse])
def listar_inventario(db: Session = Depends(get_db)):
    return db.query(Inventario).all()


# 3. Registrar lote/entrada en almacén (CU-35)
@router.post("/inventario", response_model=InventarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_lote_inventario(payload: InventarioCreate, db: Session = Depends(get_db)):
    nuevo_lote = Inventario(**payload.model_dump())
    db.add(nuevo_lote)
    db.commit()
    db.refresh(nuevo_lote)
    return nuevo_lote


@router.put("/inventario/{lote_id}", response_model=InventarioResponse)
def actualizar_lote(
    lote_id: int,
    payload: InventarioCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    lote = db.query(Inventario).filter(Inventario.id_PK == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    for campo, valor in payload.model_dump().items():
        setattr(lote, campo, valor)

    db.commit()
    db.refresh(lote)
    return lote


# 4. Evaluar Interacciones entre Medicamentos (CU-33)
@router.post("/evaluar-interacciones", response_model=EvaluarInteraccionResponse)
def evaluar_interacciones(payload: EvaluarInteraccionRequest, db: Session = Depends(get_db)):
    ids = payload.medicamentos_ids
    if len(ids) < 2:
        return {"tiene_interaccion": False, "detalles": []}

    # Buscar interacciones cruzadas entre la lista de IDs ingresada
    interacciones = db.query(InteraccionMedicamento).filter(
        or_(
            and_(
                InteraccionMedicamento.medicamento_id_FK.in_(ids),
                InteraccionMedicamento.medicamento_interactuante_id_FK.in_(ids)
            )
        )
    ).all()

    detalles = []
    for inter in interacciones:
        # Obtener nombres si la relación está cargada o fall back a IDs
        nombre_med1 = (
            inter.medicamento.nombre 
            if (inter.medicamento and hasattr(inter.medicamento, 'nombre')) 
            else f"Medicamento ID {inter.medicamento_id_FK}"
        )
        nombre_med2 = (
            inter.medicamento_interactuante.nombre 
            if (inter.medicamento_interactuante and hasattr(inter.medicamento_interactuante, 'nombre')) 
            else f"Medicamento ID {inter.medicamento_interactuante_id_FK}"
        )

        detalles.append(
            InteraccionResultado(
                medicamento_1=nombre_med1,
                medicamento_2=nombre_med2,
                severidad=inter.severidad or "No especificada",
                descripcion=inter.descripcion or "Interacción detectada entre medicamentos.",
                nivel_evidencia=inter.nivel_evidencia,
                accion_requerida=inter.accion_requerida
            )
        )

    return {
        "tiene_interaccion": len(detalles) > 0,
        "detalles": detalles
    }