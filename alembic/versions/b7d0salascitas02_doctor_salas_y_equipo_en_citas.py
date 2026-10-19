"""salas asignadas a doctores y sala/equipo en citas

Revision ID: b7d0salascitas02
Revises: a5c0ordinador01
Create Date: 2026-10-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d0salascitas02'
down_revision: Union[str, Sequence[str], None] = 'a5c0ordinador01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if 'google_event_id' not in {c['name'] for c in insp.get_columns('citas')}:
        op.add_column('citas', sa.Column('google_event_id', sa.String(255), nullable=True))
    op.create_table(
        'doctor_salas',
        sa.Column('id_PK', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('doctor_id_FK', sa.Integer(), sa.ForeignKey('doctores.id_PK'), nullable=False),
        sa.Column('sala_id_FK', sa.Integer(), sa.ForeignKey('salas.id_PK'), nullable=False),
        sa.Column('dia_semana', sa.Integer(), nullable=True),
        sa.Column('hora_inicio', sa.Time(), nullable=True),
        sa.Column('hora_fin', sa.Time(), nullable=True),
    )
    op.add_column('citas', sa.Column('sala_id_FK', sa.Integer(), nullable=True))
    op.add_column('citas', sa.Column('requiere_equipo', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('citas', sa.Column('equipo_id_FK', sa.Integer(), nullable=True))
    op.add_column('citas', sa.Column('accion_equipo', sa.Text(), nullable=True))
    op.create_foreign_key('fk_citas_sala', 'citas', 'salas', ['sala_id_FK'], ['id_PK'])
    op.create_foreign_key('fk_citas_equipo', 'citas', 'equipamiento_sala', ['equipo_id_FK'], ['id_PK'])


def downgrade() -> None:
    op.drop_constraint('fk_citas_equipo', 'citas', type_='foreignkey')
    op.drop_constraint('fk_citas_sala', 'citas', type_='foreignkey')
    op.drop_column('citas', 'accion_equipo')
    op.drop_column('citas', 'equipo_id_FK')
    op.drop_column('citas', 'requiere_equipo')
    op.drop_column('citas', 'sala_id_FK')
    op.drop_table('doctor_salas')
