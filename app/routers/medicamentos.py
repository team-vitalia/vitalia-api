from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.medicamento import Medicamento
from app.models.inventario import Inventario
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_ALMACEN, ROL_DOCTOR, ROL_RECEPCION, exigir_rol
from app.schemas.medicamento import MedicamentoCreate, MedicamentoResponse, MedicamentoUpdate
from app.services.inventario_service import expresion_stock_vigente

router = APIRouter(prefix="/api/medicamentos", tags=["Medicamentos"])


def _serializar(med: Medicamento, stock: int) -> dict:
    return {
        "id_PK": med.id_PK,
        "nombre": med.nombre,
        "presentacion": med.presentacion,
        "requiere_receta": med.requiere_receta,
        "principio_activo": med.principio_activo,
        "descripcion": med.descripcion,
        "codigo_barras": med.codigo_barras,
        "categoria": med.categoria,
        "tipo_articulo": med.tipo_articulo or "medicamento",
        "unidad_medida": med.unidad_medida,
        "stock_minimo": med.stock_minimo or 0,
        "stock_actual": int(stock) if stock else 0,
    }


@router.get("/", response_model=list[MedicamentoResponse])
def buscar_medicamentos(
    q: str | None = Query(None, description="Término de búsqueda por nombre"),
    tipo: str | None = Query(None, description="medicamento | insumo | equipo (el doctor ve solo medicamentos)"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_DOCTOR, ROL_RECEPCION, ROL_ALMACEN], "No tienes permiso")

    # `stock_actual` = unidades en lotes NO vencidos (existencia realmente disponible)
    query = (
        db.query(Medicamento, expresion_stock_vigente().label("total_stock"))
        .outerjoin(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .group_by(Medicamento.id_PK)
    )

    if usuario_actual.clinica_id_FK is not None:
        query = query.filter(Medicamento.clinica_id_FK == usuario_actual.clinica_id_FK)
    # Los médicos solo recetan medicamentos; los insumos/equipo no aparecen en su buscador
    if usuario_actual.rol_id_FK == ROL_DOCTOR and not tipo:
        tipo = "medicamento"
    if tipo:
        query = query.filter(Medicamento.tipo_articulo == tipo)
    if q:
        query = query.filter(
            Medicamento.nombre.ilike(f"%{q}%") | Medicamento.principio_activo.ilike(f"%{q}%")
        )

    resultados = query.order_by(Medicamento.nombre).limit(50).all()
    return [_serializar(med, stock) for med, stock in resultados]


@router.post("/", response_model=MedicamentoResponse, status_code=status.HTTP_201_CREATED)
def crear_medicamento(
    payload: MedicamentoCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")

    datos = payload.model_dump()
    if usuario_actual.clinica_id_FK is not None:
        datos["clinica_id_FK"] = usuario_actual.clinica_id_FK
    nuevo = Medicamento(**datos)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _serializar(nuevo, 0)


@router.put("/{medicamento_id}", response_model=MedicamentoResponse)
def actualizar_medicamento(
    medicamento_id: int,
    payload: MedicamentoUpdate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")

    med = db.query(Medicamento).filter(Medicamento.id_PK == medicamento_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    if usuario_actual.clinica_id_FK is not None and med.clinica_id_FK != usuario_actual.clinica_id_FK:
        raise HTTPException(status_code=403, detail="No tienes acceso a este medicamento")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(med, campo, valor)
    db.commit()
    db.refresh(med)

    stock = (
        db.query(expresion_stock_vigente())
        .filter(Inventario.medicamento_id_FK == med.id_PK)
        .scalar()
    )
    return _serializar(med, stock or 0)
