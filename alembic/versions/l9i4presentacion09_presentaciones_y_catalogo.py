"""presentaciones (cajas/frascos), catálogo de artículos y recetas sin stock

Revision ID: l9i4presentacion09
Revises: k8h3equipotipo08
Create Date: 2026-11-18 12:00:00.000000

* medicamentos: nombre_generico, unidades_por_presentacion, unidad_contenido
  (la unidad de presentación sigue siendo `unidad_medida`, que ya existía).
* items_receta: posología estructurada, presentaciones a surtir, nombre libre y
  marca «no disponible en farmacia».
Es idempotente: revisa con el inspector qué columnas/índices existen.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l9i4presentacion09"
down_revision: Union[str, Sequence[str], None] = "k8h3equipotipo08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS_MEDICAMENTOS = [
    sa.Column("nombre_generico", sa.String(200), nullable=True),
    sa.Column("unidades_por_presentacion", sa.Integer(), nullable=True),
    sa.Column("unidad_contenido", sa.String(30), nullable=True),
]

COLUMNAS_ITEMS = [
    sa.Column("dosis_unidades", sa.Numeric(8, 2), nullable=True),
    sa.Column("frecuencia_horas", sa.Integer(), nullable=True),
    sa.Column("duracion_dias", sa.Integer(), nullable=True),
    sa.Column("unidades_requeridas", sa.Integer(), nullable=True),
    sa.Column("cantidad_presentaciones", sa.Integer(), nullable=True),
    sa.Column("unidades_por_presentacion", sa.Integer(), nullable=True),
    sa.Column("unidad_presentacion", sa.String(30), nullable=True),
    sa.Column("unidad_contenido", sa.String(30), nullable=True),
    sa.Column("nombre_libre", sa.String(200), nullable=True),
    sa.Column("no_disponible_farmacia", sa.Boolean(), nullable=False, server_default=sa.text("0")),
]

INDICE_CODIGO = "ix_medicamentos_clinica_codigo"


def _columnas(insp, tabla: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(tabla)}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    existentes = _columnas(insp, "medicamentos")
    for col in COLUMNAS_MEDICAMENTOS:
        if col.name not in existentes:
            op.add_column("medicamentos", col.copy())

    existentes = _columnas(insp, "items_receta")
    for col in COLUMNAS_ITEMS:
        if col.name not in existentes:
            op.add_column("items_receta", col.copy())

    # Búsqueda rápida por código de barras (no único: puede haber duplicados históricos;
    # la API impide crear nuevos duplicados dentro de la misma clínica).
    indices = {i["name"] for i in insp.get_indexes("medicamentos")}
    if INDICE_CODIGO not in indices:
        op.create_index(INDICE_CODIGO, "medicamentos", ["clinica_id_FK", "codigo_barras"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())

    indices = {i["name"] for i in insp.get_indexes("medicamentos")}
    if INDICE_CODIGO in indices:
        op.drop_index(INDICE_CODIGO, table_name="medicamentos")

    existentes = _columnas(insp, "items_receta")
    for col in reversed(COLUMNAS_ITEMS):
        if col.name in existentes:
            op.drop_column("items_receta", col.name)

    existentes = _columnas(insp, "medicamentos")
    for col in reversed(COLUMNAS_MEDICAMENTOS):
        if col.name in existentes:
            op.drop_column("medicamentos", col.name)