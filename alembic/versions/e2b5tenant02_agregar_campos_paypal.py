"""Migracion para anadir identificadores de planes y suscripciones de PayPal en planes_suscripcion y clinicas.

Revision ID: e2b5tenant02
Revises: e2b5tenant01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2b5tenant02"
down_revision: Union[str, Sequence[str], None] = "e2b5tenant01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLANES_PAYPAL = [
    ("Básico", "P-61L31376NX417651DNLWUKSQ"),
    ("Clínica", "P-5CC29855SK5899208NLWUMWI"),
    ("Profesional", "P-5J121652NS326140HNLWUNNI"),
    ("Empresarial", "P-64643939B6992035JNLWUOCY"),
]


def upgrade() -> None:
    """Anade columnas de PayPal en planes_suscripcion y clinicas, y asocia los IDs de planes correspondientes."""
    op.add_column(
        "planes_suscripcion",
        sa.Column("paypal_plan_id", sa.String(100), nullable=True, unique=True)
    )
    op.add_column(
        "clinicas",
        sa.Column("paypal_subscription_id", sa.String(100), nullable=True, unique=True)
    )

    conn = op.get_bind()
    for nombre_plan, paypal_id in PLANES_PAYPAL:
        conn.execute(
            sa.text(
                "UPDATE planes_suscripcion SET paypal_plan_id = :paypal_id WHERE nombre = :nombre"
            ),
            {"paypal_id": paypal_id, "nombre": nombre_plan},
        )


def downgrade() -> None:
    """Elimina las columnas de PayPal de clinicas y planes_suscripcion."""
    op.drop_column("clinicas", "paypal_subscription_id")
    op.drop_column("planes_suscripcion", "paypal_plan_id")
