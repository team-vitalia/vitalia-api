"""Agregar cédula profesional y documento por especialidad del doctor.

Revision ID: l9m2doctor_especialidad_docs
Revises: 3bf802a28f84
Create Date: 2026-11-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "l9m2doctor_especialidad_docs"
down_revision: Union[str, Sequence[str], None] = "3bf802a28f84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("doctor_especialidades", sa.Column("cedula_profesional", sa.String(length=100), nullable=True))
    op.add_column("doctor_especialidades", sa.Column("documento_validez", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("doctor_especialidades", "documento_validez")
    op.drop_column("doctor_especialidades", "cedula_profesional")
