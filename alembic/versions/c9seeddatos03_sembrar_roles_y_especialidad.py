"""sembrar roles 1-4 y una especialidad inicial

Revision ID: c9seeddatos03
Revises: b7d0salascitas02
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9seeddatos03"
down_revision: Union[str, Sequence[str], None] = "b7d0salascitas02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = [
    (1, "Administrador", "Administración general del sistema"),
    (2, "Doctor", "Consultas, expedientes y recetas"),
    (3, "Paciente", "Consulta de sus citas e información"),
    (4, "Recepción", "Gestión de citas, pacientes y cola de espera"),
]


def upgrade() -> None:
    """Idempotente: no toca roles que ya existan (el 5 lo crea otra migración)."""
    conn = op.get_bind()
    ahora = datetime.now()

    for id_rol, nombre, descripcion in ROLES:
        existe = conn.execute(
            sa.text("SELECT COUNT(*) FROM roles WHERE id_PK = :id"), {"id": id_rol}
        ).scalar()
        if not existe:
            conn.execute(
                sa.text(
                    "INSERT INTO roles (id_PK, nombre, descripcion, creado_en, actualizado_en, esta_activo) "
                    "VALUES (:id, :nombre, :descripcion, :ahora, :ahora, 1)"
                ),
                {"id": id_rol, "nombre": nombre, "descripcion": descripcion, "ahora": ahora},
            )

    if not conn.execute(sa.text("SELECT COUNT(*) FROM especialidades")).scalar():
        conn.execute(
            sa.text(
                "INSERT INTO especialidades (nombre, descripcion, codigo, esta_activo) "
                "VALUES ('Medicina General', 'Atención médica general', 'MG', 1)"
            )
        )


def downgrade() -> None:
    """No se borran datos de catálogo que podrían estar en uso."""
    pass
