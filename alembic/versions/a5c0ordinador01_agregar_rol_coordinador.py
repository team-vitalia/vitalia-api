"""agregar rol coordinador

Revision ID: a5c0ordinador01
Revises: 52aed51e1777
Create Date: 2026-10-18 00:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5c0ordinador01'
down_revision: Union[str, Sequence[str], None] = '52aed51e1777'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Inserta el rol Coordinador (id 5) si todavía no existe."""
    conn = op.get_bind()
    existe = conn.execute(
        sa.text("SELECT COUNT(*) FROM roles WHERE nombre = 'Coordinador'")
    ).scalar()
    if not existe:
        ahora = datetime.now()
        conn.execute(
            sa.text(
                "INSERT INTO roles (id_PK, nombre, descripcion, creado_en, actualizado_en, esta_activo) "
                "VALUES (5, 'Coordinador', :descripcion, :ahora, :ahora, 1)"
            ),
            {
                "descripcion": "Coordinador operativo de VITALIA (acceso administrativo limitado)",
                "ahora": ahora,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM roles WHERE id_PK = 5 AND nombre = 'Coordinador'"))
