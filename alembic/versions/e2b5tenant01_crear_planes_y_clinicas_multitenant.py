from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2b5tenant01"
down_revision: Union[str, Sequence[str], None] = "d1a4registro04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planes_suscripcion",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(100), unique=True, nullable=False),
        sa.Column("precio_mensual", sa.Float(), nullable=False),
        sa.Column("precio_anual", sa.Float(), nullable=False),
        sa.Column("limite_personal", sa.Integer(), nullable=False),
        sa.Column("limite_pacientes", sa.Integer(), nullable=False),
        sa.Column("incluye_calendar", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("incluye_correos", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("limite_ia_mensual", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("limite_sucursales", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "clinicas",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("nombre_comercial", sa.String(200), nullable=False),
        sa.Column("plan_id_FK", sa.Integer(), sa.ForeignKey("planes_suscripcion.id_PK"), nullable=False),
        sa.Column("fecha_registro", sa.DateTime(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    conn = op.get_bind()

    planes = [
        ("Básico", 599.0, 5990.0, 3, 100, 0, 0, 0, 1),
        ("Clínica", 1199.0, 11990.0, 10, 500, 1, 1, 0, 1),
        ("Profesional", 2199.0, 21990.0, 20, 1500, 1, 1, 100, 1),
        ("Empresarial", 4499.0, 44990.0, 30, 5000, 1, 1, 500, 1),
    ]

    for p in planes:
        conn.execute(
            sa.text(
                "INSERT INTO planes_suscripcion "
                "(nombre, precio_mensual, precio_anual, limite_personal, limite_pacientes, "
                "incluye_calendar, incluye_correos, limite_ia_mensual, limite_sucursales) "
                "VALUES (:nombre, :mensual, :anual, :personal, :pacientes, :calendar, :correos, :ia, :sucursales)"
            ),
            {
                "nombre": p[0],
                "mensual": p[1],
                "anual": p[2],
                "personal": p[3],
                "pacientes": p[4],
                "calendar": p[5],
                "correos": p[6],
                "ia": p[7],
                "sucursales": p[8],
            },
        )

    plan_empresarial_id = conn.execute(
        sa.text("SELECT id_PK FROM planes_suscripcion WHERE nombre = 'Empresarial'")
    ).scalar()

    conn.execute(
        sa.text(
            "INSERT INTO clinicas (nombre_comercial, plan_id_FK, fecha_registro, activa) "
            "VALUES ('Clínica Demo', :plan_id, :fecha, 1)"
        ),
        {"plan_id": plan_empresarial_id, "fecha": datetime.now()},
    )

    demo_id = conn.execute(
        sa.text("SELECT id_PK FROM clinicas WHERE nombre_comercial = 'Clínica Demo'")
    ).scalar()

    tablas = ["usuarios", "pacientes", "citas", "salas", "medicamentos"]
    for t in tablas:
        op.add_column(t, sa.Column("clinica_id_FK", sa.Integer(), nullable=True))
        conn.execute(
            sa.text(f"UPDATE {t} SET clinica_id_FK = :demo_id WHERE clinica_id_FK IS NULL"),
            {"demo_id": demo_id},
        )
        op.alter_column(t, "clinica_id_FK", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f"fk_{t}_clinica", t, "clinicas", ["clinica_id_FK"], ["id_PK"])


def downgrade() -> None:
    tablas = ["usuarios", "pacientes", "citas", "salas", "medicamentos"]
    for t in tablas:
        op.drop_constraint(f"fk_{t}_clinica", t, type_="foreignkey")
        op.drop_column(t, "clinica_id_FK")

    op.drop_table("clinicas")
    op.drop_table("planes_suscripcion")
