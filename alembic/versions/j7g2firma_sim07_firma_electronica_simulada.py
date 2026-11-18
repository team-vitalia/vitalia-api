"""firma electrónica SIMULADA de recetas (uso académico): identidades, firmas e historial

Revision ID: j7g2firma_sim07
Revises: i6f1insumos06
Create Date: 2026-11-09 12:00:00.000000

Solo CREA tablas nuevas (no modifica ni lee las existentes), por lo que funciona
igual con `alembic upgrade head` y con `--sql` (vista previa).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "j7g2firma_sim07"
down_revision: Union[str, Sequence[str], None] = "i6f1insumos06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identidades_firma_simulada",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinica_id_FK", sa.Integer(), sa.ForeignKey("clinicas.id_PK")),
        sa.Column("usuario_id_FK", sa.Integer(), sa.ForeignKey("usuarios.id_PK"), nullable=False),
        sa.Column("nombre_ficticio", sa.String(150), nullable=False),
        sa.Column("cedula_ficticia", sa.String(30), nullable=False),
        sa.Column("especialidad_ficticia", sa.String(100)),
        sa.Column("algoritmo", sa.String(40), nullable=False, server_default="RSA-2048"),
        sa.Column("clave_publica_pem", sa.Text(), nullable=False),
        sa.Column("huella_sha256", sa.String(64), nullable=False),
        sa.Column("clave_privada_cifrada", sa.Text(), nullable=False),
        sa.Column("activa", sa.Boolean(), server_default="1"),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id_FK", name="uq_identidad_firma_usuario"),
    )

    op.create_table(
        "firmas_recetas",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codigo_verificacion", sa.String(64), nullable=False),
        sa.Column("identificador", sa.String(40), nullable=False),
        sa.Column("receta_id_FK", sa.Integer(), sa.ForeignKey("recetas.id_PK"), nullable=False),
        sa.Column("identidad_id_FK", sa.Integer(), sa.ForeignKey("identidades_firma_simulada.id_PK"), nullable=False),
        sa.Column("firmado_por_usuario_id_FK", sa.Integer(), sa.ForeignKey("usuarios.id_PK")),
        sa.Column("fecha_firma", sa.DateTime(), nullable=False),
        sa.Column("algoritmo_firma", sa.String(50), nullable=False),
        sa.Column("hash_pdf_sha256", sa.String(64), nullable=False),
        sa.Column("hash_contenido_sha256", sa.String(64), nullable=False),
        sa.Column("manifiesto_json", sa.Text(), nullable=False),
        sa.Column("firma_b64", sa.Text(), nullable=False),
        sa.Column("pdf_original", sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql"), nullable=False),
        sa.Column("tamano_pdf", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("url_verificacion", sa.String(500), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("codigo_verificacion", name="uq_firma_receta_codigo"),
        sa.UniqueConstraint("identificador", name="uq_firma_receta_identificador"),
        sa.UniqueConstraint("receta_id_FK", name="uq_firma_receta_receta"),
    )

    op.create_table(
        "historial_firmas_recetas",
        sa.Column("id_PK", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("firma_id_FK", sa.Integer(), sa.ForeignKey("firmas_recetas.id_PK"), nullable=False),
        sa.Column("receta_id_FK", sa.Integer(), sa.ForeignKey("recetas.id_PK"), nullable=False),
        sa.Column("accion", sa.String(30), nullable=False),
        sa.Column("resultado", sa.String(20)),
        sa.Column("detalle", sa.Text()),
        sa.Column("usuario_id_FK", sa.Integer(), sa.ForeignKey("usuarios.id_PK")),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("historial_firmas_recetas")
    op.drop_table("firmas_recetas")
    op.drop_table("identidades_firma_simulada")
