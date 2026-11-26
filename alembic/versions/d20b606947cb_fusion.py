"""fusion

Revision ID: d20b606947cb
Revises: f497c267d7d9, l9m2doctor_especialidad_docs
Create Date: 2026-11-25 22:07:33.710096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd20b606947cb'
down_revision: Union[str, Sequence[str], None] = ('f497c267d7d9', 'l9m2doctor_especialidad_docs')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
