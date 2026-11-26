"""agregar_signos_vitales_e_indicaciones_generales

Revision ID: f497c267d7d9
Revises: 3bf802a28f84
Create Date: 2026-11-25 18:07:48.329881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f497c267d7d9'
down_revision: Union[str, Sequence[str], None] = '3bf802a28f84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Usamos el inspector para verificar si las columnas ya existen antes de crearlas.
    # Esto evita errores si las columnas ya fueron creadas manualmente en producción.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. Agregar signos_vitales a consultas
    cols_consultas = [c["name"] for c in inspector.get_columns("consultas")]
    if "signos_vitales" not in cols_consultas:
        op.add_column("consultas", sa.Column("signos_vitales", sa.JSON(), nullable=True))
        
    # 2. Agregar indicaciones_generales a recetas
    cols_recetas = [c["name"] for c in inspector.get_columns("recetas")]
    if "indicaciones_generales" not in cols_recetas:
        op.add_column("recetas", sa.Column("indicaciones_generales", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("recetas", "indicaciones_generales")
    op.drop_column("consultas", "signos_vitales")