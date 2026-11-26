"""agregar datos doctor snapshot

Revision ID: 6e6f3c060355
Revises: 484f3d2c88d6
Create Date: 2026-11-26 15:02:40.656872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6e6f3c060355'
down_revision: Union[str, Sequence[str], None] = '484f3d2c88d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Usamos inspector para checar si la columna ya existe
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = [c["name"] for c in inspector.get_columns("recetas")]
    
    if "datos_doctor_snapshot" not in columnas:
        op.add_column("recetas", sa.Column("datos_doctor_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("recetas", "datos_doctor_snapshot")