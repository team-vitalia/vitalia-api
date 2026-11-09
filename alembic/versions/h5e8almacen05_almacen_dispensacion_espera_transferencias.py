"""rol Almacén, dispensaciones, presentaciones, lista de espera y transferencias

Revision ID: h5e8almacen05
Revises: g4d7contratos04
Create Date: 2026-11-08 00:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h5e8almacen05"
down_revision: Union[str, Sequence[str], None] = "g4d7contratos04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS_MOVIMIENTO = [
    ("Entrada", "Ingreso de unidades a un lote"),
    ("Salida", "Salida manual de unidades"),
    ("Ajuste", "Ajuste de existencias por conteo físico"),
    ("Dispensación", "Entrega de medicamento a un paciente"),
    ("Merma", "Baja por caducidad, daño o pérdida"),
]


def upgrade() -> None:
    conn = op.get_bind()
    ahora = datetime.now()

    # 1. Rol Almacén (id 6)
    existe = conn.execute(
        sa.text("SELECT COUNT(*) FROM roles WHERE id_PK = 6 OR nombre = 'Almacén'")
    ).scalar()
    if not existe:
        conn.execute(
            sa.text(
                "INSERT INTO roles (id_PK, nombre, descripcion, creado_en, actualizado_en, esta_activo) "
                "VALUES (6, 'Almacén', :d, :a, :a, 1)"
            ),
            {"d": "Medicamentos, existencias, lotes, caducidades y dispensación", "a": ahora},
        )

    # 2. Tipos de movimiento de inventario
    for nombre, descripcion in TIPOS_MOVIMIENTO:
        ya = conn.execute(
            sa.text("SELECT COUNT(*) FROM tipos_movimiento_inventario WHERE nombre = :n"),
            {"n": nombre},
        ).scalar()
        if not ya:
            conn.execute(
                sa.text(
                    "INSERT INTO tipos_movimiento_inventario (nombre, descripcion, esta_activo) "
                    "VALUES (:n, :d, 1)"
                ),
                {"n": nombre, "d": descripcion},
            )

    # 3. Ítems de receta: unidades ya dispensadas
    op.add_column(
        "items_receta",
        sa.Column("cantidad_dispensada", sa.Integer(), nullable=False, server_default="0"),
    )

    # 4. Presentaciones de medicamento
    op.create_table(
        "presentaciones_medicamento",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicamento_id_FK", sa.Integer(), sa.ForeignKey("medicamentos.id_PK"), nullable=False),
        sa.Column("concentracion", sa.String(100)),
        sa.Column("forma_farmaceutica", sa.String(100)),
        sa.Column("contenido", sa.String(100)),
        sa.Column("esta_activo", sa.Boolean(), server_default="1"),
    )

    # 5. Dispensaciones
    op.create_table(
        "dispensaciones",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinica_id_FK", sa.Integer(), sa.ForeignKey("clinicas.id_PK")),
        sa.Column("receta_id_FK", sa.Integer(), sa.ForeignKey("recetas.id_PK"), nullable=False),
        sa.Column("item_receta_id_FK", sa.Integer(), sa.ForeignKey("items_receta.id_PK"), nullable=False),
        sa.Column("inventario_id_FK", sa.Integer(), sa.ForeignKey("inventario.id_PK"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("usuario_id_FK", sa.Integer(), sa.ForeignKey("usuarios.id_PK")),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("notas", sa.Text()),
    )

    # 6. Lista de espera de citas
    op.create_table(
        "lista_espera",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinica_id_FK", sa.Integer(), sa.ForeignKey("clinicas.id_PK"), nullable=False),
        sa.Column("paciente_id_FK", sa.Integer(), sa.ForeignKey("pacientes.id_PK"), nullable=False),
        sa.Column("doctor_id_FK", sa.Integer(), sa.ForeignKey("doctores.id_PK")),
        sa.Column("especialidad_id_FK", sa.Integer(), sa.ForeignKey("especialidades.id_PK")),
        sa.Column("fecha_deseada", sa.Date()),
        sa.Column("motivo", sa.Text()),
        sa.Column("prioridad", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("estado", sa.String(30), nullable=False, server_default="en_espera"),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("atendida_en", sa.DateTime()),
        sa.Column("creado_por", sa.Integer(), sa.ForeignKey("usuarios.id_PK")),
        sa.Column("cita_id_FK", sa.Integer(), sa.ForeignKey("citas.id_PK")),
    )

    # 7. Historial de transferencias paciente ↔ médico
    op.create_table(
        "transferencias_paciente",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinica_id_FK", sa.Integer(), sa.ForeignKey("clinicas.id_PK"), nullable=False),
        sa.Column("paciente_id_FK", sa.Integer(), sa.ForeignKey("pacientes.id_PK"), nullable=False),
        sa.Column("doctor_origen_id_FK", sa.Integer(), sa.ForeignKey("doctores.id_PK"), nullable=False),
        sa.Column("doctor_destino_id_FK", sa.Integer(), sa.ForeignKey("doctores.id_PK"), nullable=False),
        sa.Column("motivo", sa.Text()),
        sa.Column("citas_reasignadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("realizado_por", sa.Integer(), sa.ForeignKey("usuarios.id_PK")),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transferencias_paciente")
    op.drop_table("lista_espera")
    op.drop_table("dispensaciones")
    op.drop_table("presentaciones_medicamento")
    op.drop_column("items_receta", "cantidad_dispensada")
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM roles WHERE id_PK = 6 AND nombre = 'Almacén'"))
