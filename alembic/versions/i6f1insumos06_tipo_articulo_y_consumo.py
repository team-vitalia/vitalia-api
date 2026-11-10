"""tipo de artículo (medicamento/insumo/equipo), unidad, stock mínimo y movimiento «Consumo»

Revision ID: i6f1insumos06
Revises: h5e8almacen05
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i6f1insumos06"
down_revision: Union[str, Sequence[str], None] = "h5e8almacen05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La tabla `medicamentos` pasa a ser el catálogo de ARTÍCULOS del almacén:
    # medicamentos, insumos (guantes, jeringas, alcohol...) y equipo (termómetros...).
    op.add_column("medicamentos", sa.Column("tipo_articulo", sa.String(20), nullable=False, server_default="medicamento"))
    op.add_column("medicamentos", sa.Column("unidad_medida", sa.String(30), nullable=True))
    op.add_column("medicamentos", sa.Column("stock_minimo", sa.Integer(), nullable=False, server_default="0"))

    # Sembrar el tipo de movimiento «Consumo» (idempotente y compatible con `--sql`:
    # no lee resultados, así que también funciona en modo de vista previa).
    op.execute(
        sa.text(
            "INSERT INTO tipos_movimiento_inventario (nombre, descripcion, esta_activo) "
            "SELECT x.nombre, x.descripcion, 1 FROM ("
            "SELECT 'Consumo' AS nombre, 'Uso interno en la clínica (insumos y material)' AS descripcion"
            ") AS x WHERE NOT EXISTS ("
            "SELECT 1 FROM tipos_movimiento_inventario t WHERE t.nombre = x.nombre)"
        )
    )


def downgrade() -> None:
    op.drop_column("medicamentos", "stock_minimo")
    op.drop_column("medicamentos", "unidad_medida")
    op.drop_column("medicamentos", "tipo_articulo")
    op.execute(sa.text("DELETE FROM tipos_movimiento_inventario WHERE nombre = 'Consumo'"))