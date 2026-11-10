"""Agregar trazabilidad de movimientos y rol Almacén.

Revision ID: h8f1almacen05
Revises: g4d7contratos04
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h8f1almacen05"
down_revision: Union[str, Sequence[str], None] = "g4d7contratos04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas_inventario = {
        columna["name"] for columna in inspector.get_columns("inventario")
    }
    if "esta_activo" not in columnas_inventario:
        op.add_column(
            "inventario",
            sa.Column("esta_activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    columnas_movimientos = {
        columna["name"] for columna in inspector.get_columns("movimientos_inventario")
    }
    if "motivo" not in columnas_movimientos:
        op.add_column(
            "movimientos_inventario",
            sa.Column("motivo", sa.String(length=255), nullable=True),
        )

    rol = conn.execute(
        sa.text("SELECT id_PK FROM roles WHERE lower(nombre) = lower(:nombre)"),
        {"nombre": "Almacén"},
    ).scalar()
    if rol is None:
        ahora = datetime.now()
        conn.execute(
            sa.text(
                "INSERT INTO roles "
                "(nombre, descripcion, creado_en, actualizado_en, esta_activo) "
                "VALUES (:nombre, :descripcion, :ahora, :ahora, 1)"
            ),
            {
                "nombre": "Almacén",
                "descripcion": "Control de lotes, caducidades, movimientos y dispensación",
                "ahora": ahora,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "motivo" in {col["name"] for col in inspector.get_columns("movimientos_inventario")}:
        op.drop_column("movimientos_inventario", "motivo")
    if "esta_activo" in {col["name"] for col in inspector.get_columns("inventario")}:
        op.drop_column("inventario", "esta_activo")
