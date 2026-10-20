from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func # 👈 Importante

from app.database.connection import get_db
from app.models.medicamento import Medicamento
from app.models.inventario import Inventario # 👈 Asegúrate de tener este modelo importado
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.schemas.medicamento import MedicamentoResponse

router = APIRouter(prefix="/api/medicamentos", tags=["Medicamentos"])

@router.get("/", response_model=list[MedicamentoResponse])
def buscar_medicamentos(
    q: str | None = Query(None, description="Término de búsqueda por nombre"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 2, 4]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # Hacemos un Left Join con inventario para sumar el stock real
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

    # Formateamos la respuesta para que incluya el stock
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