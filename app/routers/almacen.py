from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.inventario import Inventario
from app.models.interaccion_medicamento import InteraccionMedicamento
from app.models.item_receta import ItemReceta
from app.models.medicamento import Medicamento
from app.models.movimiento_inventario import MovimientoInventario
from app.models.tipo_movimiento_inventario import TipoMovimientoInventario
from app.models.usuario import Usuario
from app.schemas.almacen import (
    EvaluarInteraccionRequest,
    EvaluarInteraccionResponse,
    InteraccionResultado,
    InventarioCreate,
    InventarioResponse,
    MedicamentoResponse,
    MovimientoInventarioCreate,
    MovimientoInventarioResponse,
)

router = APIRouter(prefix="/api/almacen", tags=["Almacén e Interacciones"])
ROL_ADMINISTRADOR = 1
ROL_ALMACEN = 6
TIPOS_MOVIMIENTO = {
    "entrada": "Entrada",
    "salida": "Salida",
    "dispensacion": "Dispensación",
}


def exigir_permiso_almacen(usuario: Usuario) -> None:
    nombre_rol = (
        usuario.rol.nombre.strip().lower().replace("á", "a")
        if usuario.rol and usuario.rol.nombre
        else ""
    )
    if usuario.rol_id_FK not in (ROL_ADMINISTRADOR, ROL_ALMACEN) and nombre_rol != "almacen":
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar el almacén")


def filtrar_por_clinica(query: Any, usuario: Usuario) -> Any:
    clinica_id = getattr(usuario, "clinica_id_FK", None)
    if clinica_id is not None:
        query = query.filter(Medicamento.clinica_id_FK == clinica_id)
    return query


def consultar_lote(db: Session, lote_id: int, usuario: Usuario) -> Inventario | None:
    query = (
        db.query(Inventario)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(Inventario.id_PK == lote_id, Inventario.esta_activo.is_(True))
        .with_for_update()
    )
    return filtrar_por_clinica(query, usuario).first()


def registrar_movimiento(
    db: Session,
    lote: Inventario,
    usuario: Usuario,
    tipo: str,
    cantidad: int,
    motivo: str | None = None,
) -> None:
    nombre_tipo = TIPOS_MOVIMIENTO[tipo]
    tipo_db = (
        db.query(TipoMovimientoInventario)
        .filter(TipoMovimientoInventario.nombre.ilike(nombre_tipo))
        .first()
    )
    if not tipo_db:
        tipo_db = TipoMovimientoInventario(nombre=nombre_tipo, esta_activo=True)
        db.add(tipo_db)
        db.flush()

    anterior = int(lote.stock_actual or 0)
    nuevo = anterior + cantidad if tipo == "entrada" else anterior - cantidad
    if nuevo < 0:
        raise HTTPException(status_code=409, detail="La cantidad supera las existencias del lote")

    lote.stock_actual = nuevo
    db.add(
        MovimientoInventario(
            inventario_id_FK=lote.id_PK,
            cantidad=cantidad,
            tipo_movimiento_FK=tipo_db.id_PK,
            usuario_id_FK=usuario.id_PK,
            stock_anterior=anterior,
            stock_nuevo=nuevo,
            motivo=(motivo or "").strip() or None,
        )
    )


def lote_a_respuesta(lote: Inventario) -> dict[str, Any]:
    return {
        "id_PK": lote.id_PK,
        "medicamento_id_FK": lote.medicamento_id_FK,
        "numero_lote": lote.numero_lote,
        "stock_actual": int(lote.stock_actual or 0),
        "ubicacion": lote.ubicacion,
        "fecha_vencimiento": lote.fecha_vencimiento,
        "precio_venta": lote.precio_venta,
        "proveedor_id_FK": lote.proveedor_id_FK,
        "fecha_recepcion": lote.fecha_recepcion,
        "esta_activo": lote.esta_activo,
        "clinica_id_FK": (
            lote.medicamento.clinica_id_FK
            if isinstance(getattr(lote.medicamento, "clinica_id_FK", None), int)
            else None
        ),
    }


@router.get("/medicamentos", response_model=list[MedicamentoResponse])
def listar_medicamentos(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    query = filtrar_por_clinica(db.query(Medicamento), usuario_actual)
    return query.order_by(Medicamento.nombre).all()


@router.get("/inventario", response_model=list[InventarioResponse])
def listar_inventario(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    query = (
        db.query(Inventario)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(Inventario.esta_activo.is_(True))
    )
    lotes = filtrar_por_clinica(query, usuario_actual).order_by(Inventario.id_PK.desc()).all()
    return [lote_a_respuesta(lote) for lote in lotes]


@router.post(
    "/inventario",
    response_model=InventarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_lote_inventario(
    payload: InventarioCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    medicamento_query = db.query(Medicamento).filter(
        Medicamento.id_PK == payload.medicamento_id_FK
    )
    medicamento = filtrar_por_clinica(medicamento_query, usuario_actual).first()
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en tu clínica")
    if payload.stock_actual < 0:
        raise HTTPException(status_code=422, detail="El stock inicial no puede ser negativo")

    lote = Inventario(**payload.model_dump())
    lote.esta_activo = True
    db.add(lote)
    try:
        db.flush()
        if payload.stock_actual:
            lote.stock_actual = 0
            registrar_movimiento(
                db, lote, usuario_actual, "entrada", payload.stock_actual, "Existencia inicial del lote"
            )
        db.commit()
        db.refresh(lote)
    except Exception:
        db.rollback()
        raise
    return lote_a_respuesta(lote)


@router.put("/inventario/{lote_id}", response_model=InventarioResponse)
def actualizar_lote(
    lote_id: int,
    payload: InventarioCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    lote = consultar_lote(db, lote_id, usuario_actual)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    medicamento_query = db.query(Medicamento).filter(
        Medicamento.id_PK == payload.medicamento_id_FK
    )
    medicamento = filtrar_por_clinica(medicamento_query, usuario_actual).first()
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en tu clínica")
    if (
        payload.medicamento_id_FK != lote.medicamento_id_FK
        or payload.numero_lote != lote.numero_lote
    ):
        raise HTTPException(
            status_code=409,
            detail="El medicamento y el número de lote no se pueden cambiar; conserva la trazabilidad",
        )
    if payload.stock_actual != lote.stock_actual:
        raise HTTPException(
            status_code=409,
            detail="Usa los movimientos de entrada o salida para cambiar las existencias",
        )

    datos = payload.model_dump(exclude={"stock_actual"})
    for campo, valor in datos.items():
        setattr(lote, campo, valor)
    db.commit()
    db.refresh(lote)
    return lote_a_respuesta(lote)


@router.delete("/inventario/{lote_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_lote(
    lote_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    lote = consultar_lote(db, lote_id, usuario_actual)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if int(lote.stock_actual or 0) != 0:
        raise HTTPException(
            status_code=409,
            detail="Solo se pueden retirar lotes sin existencias; registra una salida primero",
        )
    lote.esta_activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/movimientos", response_model=list[MovimientoInventarioResponse])
def listar_movimientos(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    query = (
        db.query(
            MovimientoInventario,
            TipoMovimientoInventario.nombre,
            Usuario.nombre,
            Medicamento.nombre,
            Inventario.numero_lote,
            Medicamento.clinica_id_FK,
        )
        .join(Inventario, MovimientoInventario.inventario_id_FK == Inventario.id_PK)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .outerjoin(
            TipoMovimientoInventario,
            MovimientoInventario.tipo_movimiento_FK == TipoMovimientoInventario.id_PK,
        )
        .outerjoin(Usuario, MovimientoInventario.usuario_id_FK == Usuario.id_PK)
    )
    rows = (
        filtrar_por_clinica(query, usuario_actual)
        .order_by(MovimientoInventario.creado_en.desc(), MovimientoInventario.id_PK.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id_PK": movimiento.id_PK,
            "inventario_id_FK": movimiento.inventario_id_FK,
            "cantidad": movimiento.cantidad,
            "tipo": tipo,
            "motivo": movimiento.motivo,
            "usuario_id_FK": movimiento.usuario_id_FK,
            "usuario_nombre": usuario_nombre,
            "creado_en": movimiento.creado_en,
            "stock_anterior": movimiento.stock_anterior,
            "stock_nuevo": movimiento.stock_nuevo,
            "clinica_id_FK": clinica_id,
            "medicamento_nombre": medicamento_nombre,
            "numero_lote": numero_lote,
        }
        for (
            movimiento,
            tipo,
            usuario_nombre,
            medicamento_nombre,
            numero_lote,
            clinica_id,
        ) in rows
    ]


@router.post("/movimientos", response_model=MovimientoInventarioResponse, status_code=201)
def registrar_movimiento_inventario(
    payload: MovimientoInventarioCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_permiso_almacen(usuario_actual)
    lote = consultar_lote(db, payload.inventario_id_FK, usuario_actual)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado en tu clínica")
    if (
        payload.tipo == "dispensacion"
        and lote.fecha_vencimiento is not None
        and lote.fecha_vencimiento <= date.today()
    ):
        raise HTTPException(status_code=409, detail="No se puede dispensar un lote caducado")
    if payload.tipo != "entrada" and payload.cantidad > int(lote.stock_actual or 0):
        raise HTTPException(status_code=409, detail="La cantidad supera las existencias del lote")

    try:
        registrar_movimiento(
            db,
            lote,
            usuario_actual,
            payload.tipo,
            payload.cantidad,
            payload.motivo,
        )
        db.commit()
        db.refresh(lote)
        movimiento = (
            db.query(MovimientoInventario)
            .filter(
                MovimientoInventario.inventario_id_FK == lote.id_PK,
                MovimientoInventario.usuario_id_FK == usuario_actual.id_PK,
            )
            .order_by(MovimientoInventario.id_PK.desc())
            .first()
        )
    except Exception:
        db.rollback()
        raise

    return {
        "id_PK": movimiento.id_PK,
        "inventario_id_FK": lote.id_PK,
        "cantidad": movimiento.cantidad,
        "tipo": TIPOS_MOVIMIENTO[payload.tipo],
        "motivo": movimiento.motivo,
        "usuario_id_FK": movimiento.usuario_id_FK,
        "usuario_nombre": usuario_actual.nombre,
        "creado_en": movimiento.creado_en,
        "stock_anterior": movimiento.stock_anterior,
        "stock_nuevo": movimiento.stock_nuevo,
        "clinica_id_FK": lote.medicamento.clinica_id_FK,
        "medicamento_nombre": lote.medicamento.nombre,
        "numero_lote": lote.numero_lote,
    }


@router.post("/evaluar-interacciones", response_model=EvaluarInteraccionResponse)
def evaluar_interacciones(
    payload: EvaluarInteraccionRequest,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    ids = list(set(payload.medicamentos_ids))
    if len(ids) < 2:
        return {"tiene_interaccion": False, "detalles": []}

    consulta = db.query(Medicamento.id_PK).filter(Medicamento.id_PK.in_(ids))
    ids_clinica = {
        fila[0] for fila in filtrar_por_clinica(consulta, usuario_actual).all()
    }
    if ids_clinica != set(ids):
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en tu clínica")

    interacciones = (
        db.query(InteraccionMedicamento)
        .filter(
            InteraccionMedicamento.medicamento_id_FK.in_(ids),
            InteraccionMedicamento.medicamento_interactuante_id_FK.in_(ids),
        )
        .all()
    )
    detalles = [
        InteraccionResultado(
            medicamento_1=(
                inter.medicamento.nombre
                if inter.medicamento
                else f"Medicamento ID {inter.medicamento_id_FK}"
            ),
            medicamento_2=(
                inter.medicamento_interactuante.nombre
                if inter.medicamento_interactuante
                else f"Medicamento ID {inter.medicamento_interactuante_id_FK}"
            ),
            severidad=inter.severidad or "No especificada",
            descripcion=inter.descripcion or "Interacción detectada entre medicamentos.",
            nivel_evidencia=inter.nivel_evidencia,
            accion_requerida=inter.accion_requerida,
        )
        for inter in interacciones
    ]
    return {"tiene_interaccion": bool(detalles), "detalles": detalles}
