"""merge

Revision ID: 3bf802a28f84
Revises: k8h3equipotipo08, k8h3suscripcion08
Create Date: 2026-11-19 16:38:21.177249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3bf802a28f84'
down_revision: Union[str, Sequence[str], None] = ('k8h3equipotipo08', 'k8h3suscripcion08')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
