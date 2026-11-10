from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database.connection import get_db
from app.models.medicamento import Medicamento
from app.models.inventario import Inventario
from app.models.item_receta import ItemReceta
from app.models.interaccion_medicamento import InteraccionMedicamento
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.schemas.medicamento import MedicamentoResponse, MedicamentoCreate

router = APIRouter(prefix="/api/medicamentos", tags=["Medicamentos"])


def puede_gestionar_almacen(usuario: Usuario) -> bool:
    nombre_rol = (
        usuario.rol.nombre.strip().lower().replace("á", "a")
        if usuario.rol and usuario.rol.nombre
        else ""
    )
    return usuario.rol_id_FK == 1 or usuario.rol_id_FK == 6 or nombre_rol == "almacen"


@router.get("/", response_model=list[MedicamentoResponse])
def buscar_medicamentos(
    q: str | None = Query(None, description="Término de búsqueda por nombre"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if usuario_actual.rol_id_FK not in [1, 2, 4] and not puede_gestionar_almacen(usuario_actual):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    query = (
        db.query(
            Medicamento,
            func.coalesce(func.sum(Inventario.stock_actual), 0).label("total_stock")
        )
        .outerjoin(
            Inventario,
            and_(
                Inventario.medicamento_id_FK == Medicamento.id_PK,
                Inventario.esta_activo.is_(True),
            ),
        )
        .group_by(Medicamento.id_PK)
    )
    
    if usuario_actual.clinica_id_FK is not None:
        query = query.filter(Medicamento.clinica_id_FK == usuario_actual.clinica_id_FK)
    if q:
        query = query.filter(Medicamento.nombre.ilike(f"%{q}%"))
        
    resultados = query.order_by(Medicamento.nombre).limit(50).all()

    return [
        {
            "id_PK": med.id_PK,
            "nombre": med.nombre,
            "principio_activo": med.principio_activo,
            "presentacion": med.presentacion,
            "requiere_receta": med.requiere_receta,
            "descripcion": med.descripcion,
            "codigo_barras": med.codigo_barras,
            "categoria": med.categoria,
            "stock_actual": int(stock) if stock else 0,
            "clinica_id_FK": med.clinica_id_FK,
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
    if not puede_gestionar_almacen(usuario_actual):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    datos = payload.model_dump()
    if usuario_actual.clinica_id_FK is not None:
        datos["clinica_id_FK"] = usuario_actual.clinica_id_FK
    nuevo = Medicamento(**datos)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "id_PK": nuevo.id_PK,
        "nombre": nuevo.nombre,
        "principio_activo": nuevo.principio_activo,
        "presentacion": nuevo.presentacion,
        "requiere_receta": nuevo.requiere_receta,
        "descripcion": nuevo.descripcion,
        "codigo_barras": nuevo.codigo_barras,
        "categoria": nuevo.categoria,
        "stock_actual": 0,
        "clinica_id_FK": nuevo.clinica_id_FK,
    }


@router.delete("/{medicamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_medicamento(
    medicamento_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    if not puede_gestionar_almacen(usuario_actual):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    query = db.query(Medicamento).filter(Medicamento.id_PK == medicamento_id)
    if usuario_actual.clinica_id_FK is not None:
        query = query.filter(Medicamento.clinica_id_FK == usuario_actual.clinica_id_FK)
    medicamento = query.first()
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en tu clínica")

    tiene_lotes = db.query(Inventario.id_PK).filter(
        Inventario.medicamento_id_FK == medicamento.id_PK
    ).first()
    tiene_recetas = db.query(ItemReceta.id_PK).filter(
        ItemReceta.medicamento_id_FK == medicamento.id_PK
    ).first()
    tiene_interacciones = db.query(InteraccionMedicamento.id_PK).filter(
        (InteraccionMedicamento.medicamento_id_FK == medicamento.id_PK)
        | (InteraccionMedicamento.medicamento_interactuante_id_FK == medicamento.id_PK)
    ).first()
    if tiene_lotes or tiene_recetas or tiene_interacciones:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el medicamento tiene lotes, recetas o interacciones registradas",
        )

    db.delete(medicamento)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)