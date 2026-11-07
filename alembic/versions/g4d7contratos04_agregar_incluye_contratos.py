from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "g4d7contratos04"
down_revision: Union[str, Sequence[str], None] = "f3c6superadmin03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columnas = [col["name"] for col in insp.get_columns("planes_suscripcion")]

    if "incluye_contratos" not in columnas:
        op.add_column(
            "planes_suscripcion",
            sa.Column(
                "incluye_contratos",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    conn.execute(
        sa.text("UPDATE planes_suscripcion SET incluye_contratos = 1 WHERE nombre = 'Empresarial'")
    )
    conn.execute(
        sa.text("UPDATE planes_suscripcion SET incluye_contratos = 0 WHERE nombre != 'Empresarial'")
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columnas = [col["name"] for col in insp.get_columns("planes_suscripcion")]

    if "incluye_contratos" in columnas:
        op.drop_column("planes_suscripcion", "incluye_contratos")
