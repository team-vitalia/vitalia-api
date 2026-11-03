from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.models.medicamento import Medicamento
from app.models.inventario import Inventario
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.schemas.medicamento import MedicamentoResponse, MedicamentoCreate

router = APIRouter(prefix="/api/medicamentos", tags=["Medicamentos"])

@router.get("/", response_model=list[MedicamentoResponse])
def buscar_medicamentos(
    q: str | None = Query(None, description="Término de búsqueda por nombre"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    query = (
        db.query(
            Medicamento,
            func.coalesce(func.sum(Inventario.stock_actual), 0).label("total_stock")
        )
        .outerjoin(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .group_by(Medicamento.id_PK)
    )
    
    if q:
        query = query.filter(Medicamento.nombre.ilike(f"%{q}%"))
        
    resultados = query.order_by(Medicamento.nombre).limit(50).all()

    return [
        {
            "id_PK": med.id_PK,
            "nombre": med.nombre,
            "presentacion": med.presentacion,
            "requiere_receta": med.requiere_receta,
            "stock_actual": int(stock) if stock else 0
        }
        for med, stock in resultados
    ]


@router.post("/", response_model=MedicamentoResponse, status_code=status.HTTP_201_CREATED)
def crear_medicamento(
    payload: MedicamentoCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    # Cambia 1 si el ID del rol administrador en tu sistema es diferente.
    if usuario_actual.rol_id_FK != 1:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    nuevo = Medicamento(**payload.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "id_PK": nuevo.id_PK,
        "nombre": nuevo.nombre,
        "presentacion": nuevo.presentacion,
        "requiere_receta": nuevo.requiere_receta,
        "stock_actual": 0,
    }