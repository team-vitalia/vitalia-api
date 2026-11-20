"""Consultas del catálogo de artículos: código de barras, duplicados y alternativas."""
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.services import inventario_service as inv


def normalizar_codigo(codigo: str | None) -> str | None:
    """Quita espacios y caracteres de control (los lectores a veces añaden saltos)."""
    if codigo is None:
        return None
    limpio = "".join(ch for ch in str(codigo) if ch.isprintable() and not ch.isspace())
    return limpio or None


def variantes_codigo(codigo: str | None) -> list[str]:
    """Formas equivalentes de un mismo GTIN.

    Un UPC-A (12 dígitos) puede leerse como EAN-13 con un 0 al frente, y un GTIN-14
    contiene al EAN-13 con ceros a la izquierda. Se prueban todas.
    """
    c = normalizar_codigo(codigo)
    if not c:
        return []
    variantes = [c]
    if c.isdigit():
        base = c.lstrip("0") or "0"
        variantes.append(base)
        for largo in (8, 12, 13, 14):
            if len(base) <= largo:
                variantes.append(base.zfill(largo))
    return list(dict.fromkeys(variantes))


def inventario_en_uso(db: Session, clinica_id: int | None) -> bool:
    """¿La clínica ya registró algún lote? Si no, no se alerta de «sin existencias»."""
    q = db.query(Inventario.id_PK).join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    return q.first() is not None


def articulo_por_codigo(
    db: Session, codigo: str, clinica_id: int | None, tipo: str | None = None
) -> Medicamento | None:
    variantes = variantes_codigo(codigo)
    if not variantes:
        return None
    q = db.query(Medicamento).filter(Medicamento.codigo_barras.in_(variantes))
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    if tipo:
        q = q.filter(Medicamento.tipo_articulo == tipo)
    return q.order_by(Medicamento.id_PK).first()


def articulo_con_codigo_duplicado(
    db: Session, codigo: str | None, clinica_id: int | None, excluir_id: int | None = None
) -> Medicamento | None:
    """Artículo de la misma clínica que ya usa ese código de barras (o None)."""
    variantes = variantes_codigo(codigo)
    if not variantes:
        return None
    q = db.query(Medicamento).filter(Medicamento.codigo_barras.in_(variantes))
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    if excluir_id is not None:
        q = q.filter(Medicamento.id_PK != excluir_id)
    return q.first()


def alternativas_de(db: Session, med: Medicamento, limite: int = 10) -> list[tuple[Medicamento, int]]:
    """Medicamentos con el mismo principio activo / nombre genérico y existencias vigentes."""
    claves = {c.strip().lower() for c in (med.principio_activo, med.nombre_generico) if c and c.strip()}
    if not claves:
        return []
    condiciones = []
    for clave in claves:
        condiciones.append(func.lower(Medicamento.principio_activo) == clave)
        condiciones.append(func.lower(Medicamento.nombre_generico) == clave)

    stock = inv.expresion_stock_vigente()
    filas = (
        db.query(Medicamento, stock.label("stock"))
        .outerjoin(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(
            Medicamento.id_PK != med.id_PK,
            Medicamento.clinica_id_FK == med.clinica_id_FK,
            Medicamento.tipo_articulo == "medicamento",
            or_(*condiciones),
        )
        .group_by(Medicamento.id_PK)
        .having(stock > 0)
        .order_by(stock.desc(), Medicamento.nombre)
        .limit(limite)
        .all()
    )
    return [(m, int(s or 0)) for m, s in filas]