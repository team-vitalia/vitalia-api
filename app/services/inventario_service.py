"""Reglas de inventario: existencias vigentes, movimientos y dispensación.

* Un registro de `inventario` representa un LOTE (numero_lote + fecha_vencimiento).
* Las existencias "disponibles" excluyen lotes vencidos.
* La dispensación consume lotes con criterio FEFO (primero en vencer, primero en salir).
"""
from datetime import date

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.dispensacion import Dispensacion
from app.models.inventario import Inventario
from app.models.item_receta import ItemReceta
from app.models.medicamento import Medicamento
from app.models.movimiento_inventario import MovimientoInventario
from app.models.receta import Receta
from app.models.tipo_movimiento_inventario import TipoMovimientoInventario

TIPO_ENTRADA = "Entrada"
TIPO_SALIDA = "Salida"
TIPO_AJUSTE = "Ajuste"
TIPO_DISPENSACION = "Dispensación"
TIPO_MERMA = "Merma"

ESTADO_RECETA_ACTIVA = "activa"
ESTADO_RECETA_PARCIAL = "dispensada_parcial"
ESTADO_RECETA_DISPENSADA = "dispensada"
ESTADO_RECETA_CANCELADA = "cancelada"


class InventarioError(Exception):
    """Error de regla de negocio; el router lo convierte en HTTPException."""

    def __init__(self, detalle: str, status_code: int = 400):
        super().__init__(detalle)
        self.detalle = detalle
        self.status_code = status_code


# ---------------------------------------------------------------- existencias
def _es_vigente():
    return or_(
        Inventario.fecha_vencimiento.is_(None),
        Inventario.fecha_vencimiento >= date.today(),
    )


def stock_disponible(db: Session, medicamento_id: int) -> int:
    """Unidades en lotes NO vencidos."""
    total = (
        db.query(func.coalesce(func.sum(Inventario.stock_actual), 0))
        .filter(
            Inventario.medicamento_id_FK == medicamento_id,
            Inventario.stock_actual > 0,
            _es_vigente(),
        )
        .scalar()
    )
    return int(total or 0)


def expresion_stock_vigente():
    """Expresión SQL para sumar solo stock vigente (para consultas agrupadas)."""
    return func.coalesce(
        func.sum(
            case(
                (_es_vigente(), Inventario.stock_actual),
                else_=0,
            )
        ),
        0,
    )


def lotes_fefo(db: Session, medicamento_id: int, bloquear: bool = False) -> list[Inventario]:
    q = (
        db.query(Inventario)
        .filter(
            Inventario.medicamento_id_FK == medicamento_id,
            Inventario.stock_actual > 0,
            _es_vigente(),
        )
        .order_by(Inventario.fecha_vencimiento.is_(None), Inventario.fecha_vencimiento.asc(), Inventario.id_PK.asc())
    )
    if bloquear:
        q = q.with_for_update()
    return q.all()


# ---------------------------------------------------------------- movimientos
def obtener_tipo_movimiento(db: Session, nombre: str) -> TipoMovimientoInventario:
    tipo = db.query(TipoMovimientoInventario).filter(TipoMovimientoInventario.nombre == nombre).first()
    if not tipo:
        tipo = TipoMovimientoInventario(nombre=nombre, esta_activo=True)
        db.add(tipo)
        db.flush()
    return tipo


def registrar_movimiento(
    db: Session,
    lote: Inventario,
    cantidad: int,
    tipo_nombre: str,
    usuario_id: int | None,
    stock_anterior: int,
    stock_nuevo: int,
    referencia: int | None = None,
) -> MovimientoInventario:
    """Agrega un movimiento (el commit lo hace el llamador)."""
    tipo = obtener_tipo_movimiento(db, tipo_nombre)
    mov = MovimientoInventario(
        inventario_id_FK=lote.id_PK,
        cantidad=cantidad,
        tipo_movimiento_FK=tipo.id_PK,
        usuario_id_FK=usuario_id,
        id_referencia=referencia,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
    )
    db.add(mov)
    return mov


def aplicar_movimiento_manual(
    db: Session,
    lote: Inventario,
    tipo: str,
    cantidad: int,
    usuario_id: int | None,
) -> MovimientoInventario:
    """Entrada / salida / merma / ajuste sobre un lote.

    * entrada: suma `cantidad`.
    * salida y merma: restan `cantidad` (no pueden dejar el stock negativo).
    * ajuste: fija el stock EXACTO en `cantidad` (conteo físico).
    """
    tipo = tipo.strip().lower()
    anterior = int(lote.stock_actual or 0)

    if tipo == "entrada":
        if cantidad <= 0:
            raise InventarioError("La cantidad de una entrada debe ser mayor a 0")
        nuevo, nombre, delta = anterior + cantidad, TIPO_ENTRADA, cantidad
    elif tipo in ("salida", "merma"):
        if cantidad <= 0:
            raise InventarioError("La cantidad debe ser mayor a 0")
        if cantidad > anterior:
            raise InventarioError(
                f"Existencias insuficientes en el lote (hay {anterior}, se piden {cantidad})", 409
            )
        nuevo = anterior - cantidad
        nombre = TIPO_MERMA if tipo == "merma" else TIPO_SALIDA
        delta = -cantidad
    elif tipo == "ajuste":
        if cantidad < 0:
            raise InventarioError("El stock ajustado no puede ser negativo")
        nuevo, nombre, delta = cantidad, TIPO_AJUSTE, cantidad - anterior
    else:
        raise InventarioError("Tipo inválido. Usa: entrada, salida, merma o ajuste", 422)

    lote.stock_actual = nuevo
    return registrar_movimiento(db, lote, delta, nombre, usuario_id, anterior, nuevo)


# ---------------------------------------------------------------- recetas
def pendiente_item(item: ItemReceta) -> int:
    return max(int(item.cantidad or 0) - int(item.cantidad_dispensada or 0), 0)


def disponibilidad_item(db: Session, item: ItemReceta) -> dict:
    """Estado de disponibilidad de un ítem de receta contra el inventario."""
    pendiente = pendiente_item(item)
    stock = stock_disponible(db, item.medicamento_id_FK) if item.medicamento_id_FK else 0

    if pendiente == 0:
        estado = "dispensado"
    elif stock >= pendiente:
        estado = "disponible"
    elif stock > 0:
        estado = "parcial"
    else:
        estado = "no_disponible"

    med = item.medicamento
    return {
        "item_receta_id": item.id_PK,
        "medicamento_id": item.medicamento_id_FK,
        "medicamento": med.nombre if med else None,
        "presentacion": med.presentacion if med else None,
        "cantidad_recetada": int(item.cantidad or 0),
        "cantidad_dispensada": int(item.cantidad_dispensada or 0),
        "cantidad_pendiente": pendiente,
        "stock_disponible": stock,
        "estado": estado,
    }


def disponibilidad_receta(db: Session, items: list[ItemReceta]) -> list[dict]:
    return [disponibilidad_item(db, it) for it in items]


def _recalcular_estado_receta(receta: Receta, items: list[ItemReceta]) -> None:
    if receta.estado == ESTADO_RECETA_CANCELADA:
        return
    if all(pendiente_item(it) == 0 for it in items):
        receta.estado = ESTADO_RECETA_DISPENSADA
    elif any(int(it.cantidad_dispensada or 0) > 0 for it in items):
        receta.estado = ESTADO_RECETA_PARCIAL
    else:
        receta.estado = ESTADO_RECETA_ACTIVA


def dispensar_receta(
    db: Session,
    receta: Receta,
    items: list[ItemReceta],
    usuario_id: int,
    clinica_id: int | None,
    solicitudes: dict[int, int] | None = None,
    notas: str | None = None,
) -> dict:
    """Dispensa una receta descontando lotes FEFO.

    solicitudes=None  → dispensa lo que haya de TODO lo pendiente (puede ser parcial).
    solicitudes={id: n} → dispensa exactamente n por ítem; si no alcanza, 409.
    El commit lo hace el llamador.
    """
    if receta.estado == ESTADO_RECETA_CANCELADA:
        raise InventarioError("La receta está cancelada", 409)
    if receta.estado == ESTADO_RECETA_DISPENSADA:
        raise InventarioError("La receta ya fue dispensada por completo", 409)

    por_id = {it.id_PK: it for it in items}
    if solicitudes is not None:
        for item_id in solicitudes:
            if item_id not in por_id:
                raise InventarioError(f"El ítem {item_id} no pertenece a la receta", 404)
        objetivo = {por_id[i]: n for i, n in solicitudes.items()}
    else:
        objetivo = {it: None for it in items}

    # 1. Calcular lo que se entregará por ítem (y validar antes de tocar nada)
    plan: list[tuple[ItemReceta, int]] = []
    for item, pedido in objetivo.items():
        pendiente = pendiente_item(item)
        if pendiente == 0:
            continue
        stock = stock_disponible(db, item.medicamento_id_FK)
        if pedido is None:
            entregar = min(pendiente, stock)
        else:
            if pedido <= 0:
                raise InventarioError("La cantidad a dispensar debe ser mayor a 0", 422)
            if pedido > pendiente:
                raise InventarioError(
                    f"Se intenta dispensar {pedido} pero solo quedan {pendiente} pendientes del ítem {item.id_PK}", 400
                )
            if pedido > stock:
                nombre = item.medicamento.nombre if item.medicamento else f"ID {item.medicamento_id_FK}"
                raise InventarioError(
                    f"Existencias insuficientes de {nombre} (hay {stock}, se piden {pedido})", 409
                )
            entregar = pedido
        if entregar > 0:
            plan.append((item, entregar))

    if not plan:
        raise InventarioError("No hay existencias disponibles para dispensar esta receta", 409)

    # 2. Descontar lotes FEFO y registrar movimientos
    registros: list[Dispensacion] = []
    for item, entregar in plan:
        restante = entregar
        for lote in lotes_fefo(db, item.medicamento_id_FK, bloquear=True):
            if restante == 0:
                break
            tomar = min(restante, int(lote.stock_actual or 0))
            if tomar <= 0:
                continue
            anterior = int(lote.stock_actual)
            lote.stock_actual = anterior - tomar
            registrar_movimiento(
                db, lote, -tomar, TIPO_DISPENSACION, usuario_id,
                anterior, lote.stock_actual, referencia=receta.id_PK,
            )
            disp = Dispensacion(
                clinica_id_FK=clinica_id,
                receta_id_FK=receta.id_PK,
                item_receta_id_FK=item.id_PK,
                inventario_id_FK=lote.id_PK,
                cantidad=tomar,
                usuario_id_FK=usuario_id,
                notas=notas,
            )
            db.add(disp)
            registros.append(disp)
            restante -= tomar
        if restante > 0:
            # Carrera: otro proceso consumió el stock entre la validación y el descuento
            raise InventarioError("Las existencias cambiaron durante la dispensación; intenta de nuevo", 409)
        item.cantidad_dispensada = int(item.cantidad_dispensada or 0) + entregar

    _recalcular_estado_receta(receta, items)
    db.flush()

    faltantes = [
        {
            "item_receta_id": it.id_PK,
            "medicamento": it.medicamento.nombre if it.medicamento else None,
            "cantidad_pendiente": pendiente_item(it),
        }
        for it in items
        if pendiente_item(it) > 0
    ]
    return {"dispensaciones": registros, "faltantes": faltantes, "estado_receta": receta.estado}


# ---------------------------------------------------------------- consumo interno
TIPO_CONSUMO = "Consumo"


def consumir_fefo(
    db: Session,
    medicamento_id: int,
    cantidad: int,
    tipo_nombre: str,
    usuario_id: int | None,
    referencia: int | None = None,
) -> list[tuple[Inventario, int]]:
    """Descuenta `cantidad` de un artículo tomando lotes FEFO (primero en vencer).

    Sirve para uso interno de insumos (guantes, jeringas, alcohol...) y deja un
    movimiento por lote. Devuelve [(lote, unidades_tomadas)]. El commit lo hace el llamador.
    """
    if cantidad <= 0:
        raise InventarioError("La cantidad debe ser mayor a 0", 422)
    stock = stock_disponible(db, medicamento_id)
    if cantidad > stock:
        raise InventarioError(f"Existencias insuficientes (hay {stock}, se piden {cantidad})", 409)

    restante = cantidad
    usados: list[tuple[Inventario, int]] = []
    for lote in lotes_fefo(db, medicamento_id, bloquear=True):
        if restante == 0:
            break
        tomar = min(restante, int(lote.stock_actual or 0))
        if tomar <= 0:
            continue
        anterior = int(lote.stock_actual)
        lote.stock_actual = anterior - tomar
        registrar_movimiento(
            db, lote, -tomar, tipo_nombre, usuario_id, anterior, lote.stock_actual, referencia=referencia
        )
        usados.append((lote, tomar))
        restante -= tomar
    if restante > 0:
        raise InventarioError("Las existencias cambiaron durante el consumo; intenta de nuevo", 409)
    return usados
