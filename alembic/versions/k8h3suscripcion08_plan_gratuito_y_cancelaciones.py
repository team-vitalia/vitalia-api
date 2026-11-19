from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "k8h3suscripcion08"
down_revision: Union[str, Sequence[str], None] = "j7g2googleauth07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    cols_planes = [col["name"] for col in insp.get_columns("planes_suscripcion")]

    if "limite_pacientes_mes" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("limite_pacientes_mes", sa.Integer(), nullable=True, server_default=None),
        )

    if "incluye_salas" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("incluye_salas", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "incluye_almacen" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("incluye_almacen", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "incluye_reportes" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("incluye_reportes", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "incluye_auditoria" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("incluye_auditoria", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "incluye_roles" not in cols_planes:
        op.add_column(
            "planes_suscripcion",
            sa.Column("incluye_roles", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    cols_clinicas = [col["name"] for col in insp.get_columns("clinicas")]

    if "fecha_inicio_suscripcion" not in cols_clinicas:
        op.add_column(
            "clinicas",
            sa.Column("fecha_inicio_suscripcion", sa.DateTime(), nullable=True),
        )

    if "ultimo_pago_capture_id" not in cols_clinicas:
        op.add_column(
            "clinicas",
            sa.Column("ultimo_pago_capture_id", sa.String(100), nullable=True),
        )

    cols_pacientes = [col["name"] for col in insp.get_columns("pacientes")]
    if "creado_en" not in cols_pacientes:
        op.add_column(
            "pacientes",
            sa.Column("creado_en", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        )

    tablas = insp.get_table_names()
    if "cancelaciones_suscripcion" not in tablas:
        op.create_table(
            "cancelaciones_suscripcion",
            sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("clinica_id_FK", sa.Integer(), sa.ForeignKey("clinicas.id_PK", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_anterior_id_FK", sa.Integer(), sa.ForeignKey("planes_suscripcion.id_PK"), nullable=False),
            sa.Column("fecha_cancelacion", sa.DateTime(), nullable=False),
            sa.Column("motivo_categoria", sa.String(50), nullable=False),
            sa.Column("comentarios_adicionales", sa.Text(), nullable=True),
            sa.Column("aplica_reembolso", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("estado_reembolso", sa.String(30), nullable=False, server_default="NO_APLICA"),
            sa.Column("paypal_refund_id", sa.String(100), nullable=True),
        )

    plan_gratuito = conn.execute(
        sa.text("SELECT id_PK FROM planes_suscripcion WHERE nombre = 'Gratuito'")
    ).fetchone()

    if not plan_gratuito:
        conn.execute(
            sa.text(
                "INSERT INTO planes_suscripcion ("
                "nombre, precio_mensual, precio_anual, limite_personal, limite_pacientes, "
                "limite_pacientes_mes, incluye_calendar, incluye_correos, limite_ia_mensual, "
                "limite_sucursales, incluye_contratos, incluye_salas, incluye_almacen, "
                "incluye_reportes, incluye_auditoria, incluye_roles, paypal_plan_id"
                ") VALUES ("
                "'Gratuito', 0.00, 0.00, 1, 20, 20, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, NULL"
                ")"
            )
        )
    else:
        conn.execute(
            sa.text(
                "UPDATE planes_suscripcion SET "
                "precio_mensual = 0.00, "
                "precio_anual = 0.00, "
                "limite_personal = 1, "
                "limite_pacientes = 20, "
                "limite_pacientes_mes = 20, "
                "incluye_calendar = 0, "
                "incluye_correos = 0, "
                "limite_ia_mensual = 0, "
                "incluye_contratos = 0, "
                "incluye_salas = 0, "
                "incluye_almacen = 0, "
                "incluye_reportes = 0, "
                "incluye_auditoria = 0, "
                "incluye_roles = 0, "
                "paypal_plan_id = NULL "
                "WHERE nombre = 'Gratuito'"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    tablas = insp.get_table_names()
    if "cancelaciones_suscripcion" in tablas:
        op.drop_table("cancelaciones_suscripcion")

    cols_clinicas = [col["name"] for col in insp.get_columns("clinicas")]
    if "ultimo_pago_capture_id" in cols_clinicas:
        op.drop_column("clinicas", "ultimo_pago_capture_id")
    if "fecha_inicio_suscripcion" in cols_clinicas:
        op.drop_column("clinicas", "fecha_inicio_suscripcion")

    cols_planes = [col["name"] for col in insp.get_columns("planes_suscripcion")]
    for col in [
        "incluye_roles",
        "incluye_auditoria",
        "incluye_reportes",
        "incluye_almacen",
        "incluye_salas",
        "limite_pacientes_mes",
    ]:
        if col in cols_planes:
            op.drop_column("planes_suscripcion", col)
