from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j7g2googleauth07"
down_revision: Union[str, Sequence[str], None] = "i6f1insumos06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("auth_provider", sa.String(50), nullable=True, server_default="manual"))
    op.alter_column("usuarios", "hash_contrasena", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.alter_column("usuarios", "hash_contrasena", existing_type=sa.String(255), nullable=False)
    op.drop_column("usuarios", "auth_provider")
