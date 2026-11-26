"""agregar_cedulas_doctor_especialidades

Revision ID: 484f3d2c88d6
Revises: d20b606947cb
Create Date: 2026-11-26 13:17:03.468891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '484f3d2c88d6'
down_revision: Union[str, Sequence[str], None] = 'd20b606947cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Verificamos si las columnas ya existen para no romper nada
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = [c["name"] for c in inspector.get_columns("doctor_especialidades")]
    
    if "cedula_profesional" not in columnas:
        op.add_column("doctor_especialidades", sa.Column("cedula_profesional", sa.String(length=50), nullable=True))
        
    if "documento_validez" not in columnas:
        op.add_column("doctor_especialidades", sa.Column("documento_validez", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("doctor_especialidades", "documento_validez")
    op.drop_column("doctor_especialidades", "cedula_profesional")