from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4registro04"
down_revision: Union[str, Sequence[str], None] = "c9seeddatos03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # usuarios
    op.add_column("usuarios", sa.Column("apellido_paterno", sa.String(length=100), nullable=True))
    op.add_column("usuarios", sa.Column("apellido_materno", sa.String(length=100), nullable=True))

    # pacientes
    op.add_column("pacientes", sa.Column("apellido_paterno", sa.String(length=100), nullable=True))
    op.add_column("pacientes", sa.Column("apellido_materno", sa.String(length=100), nullable=True))
    op.add_column("pacientes", sa.Column("curp", sa.String(length=18), nullable=True))
    op.create_unique_constraint("uq_pacientes_curp", "pacientes", ["curp"])

    # doctores
    op.add_column("doctores", sa.Column("rfc", sa.String(length=13), nullable=True))

    # Datos existentes: conservar el apellido actual como apellido paterno.
    op.execute(
        "UPDATE pacientes SET apellido_paterno = apellido "
        "WHERE apellido_paterno IS NULL AND apellido IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("doctores", "rfc")

    op.drop_constraint("uq_pacientes_curp", "pacientes", type_="unique")
    op.drop_column("pacientes", "curp")
    op.drop_column("pacientes", "apellido_materno")
    op.drop_column("pacientes", "apellido_paterno")

    op.drop_column("usuarios", "apellido_materno")
    op.drop_column("usuarios", "apellido_paterno")
