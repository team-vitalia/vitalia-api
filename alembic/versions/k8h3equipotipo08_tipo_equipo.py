"""tipo de equipo (icono/categoría) en equipamiento_sala

Revision ID: k8h3equipotipo08
Revises: j7g2googleauth07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k8h3equipotipo08"
down_revision: Union[str, Sequence[str], None] = "j7g2googleauth07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    columnas = {c["name"] for c in insp.get_columns("equipamiento_sala")}
    if "tipo_equipo" not in columnas:
        op.add_column("equipamiento_sala", sa.Column("tipo_equipo", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("equipamiento_sala", "tipo_equipo")
