"""Migracion para sembrar el usuario SuperAdmin inicial y asegurar la clinica base.

Revision ID: f3c6superadmin03
Revises: e2b5tenant02
"""

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3c6superadmin03"
down_revision: Union[str, Sequence[str], None] = "e2b5tenant02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUPERADMIN_EMAIL = "superadmin@vitalia.com"
SUPERADMIN_HASH = "$2b$12$rQe20WhjaPiZckcKsTp/2.LHAwjBIDSHGriuaVfAuqHdkBWpJEWL6"


def upgrade() -> None:
    """Inserta o actualiza el registro del Super Administrador con acceso al Backoffice."""
    conn = op.get_bind()

    rol = conn.execute(
        sa.text("SELECT id_PK FROM roles WHERE id_PK = 1")
    ).fetchone()
    if not rol:
        conn.execute(
            sa.text(
                "INSERT INTO roles (id_PK, nombre, descripcion, esta_activo, creado_en, actualizado_en) "
                "VALUES (1, 'Administrador', 'Rol principal de administracion', 1, NOW(), NOW())"
            )
        )

    clinica = conn.execute(
        sa.text("SELECT id_PK FROM clinicas WHERE id_PK = 1")
    ).fetchone()
    if not clinica:
        plan = conn.execute(
            sa.text("SELECT id_PK FROM planes_suscripcion ORDER BY id_PK DESC LIMIT 1")
        ).fetchone()
        plan_id = plan[0] if plan else 1
        conn.execute(
            sa.text(
                "INSERT INTO clinicas (id_PK, nombre_comercial, plan_id_FK, fecha_registro, activa) "
                "VALUES (1, 'Clínica Demo', :plan_id, NOW(), 1)"
            ),
            {"plan_id": plan_id},
        )

    usuario = conn.execute(
        sa.text("SELECT id_PK FROM usuarios WHERE correo_electronico = :correo"),
        {"correo": SUPERADMIN_EMAIL},
    ).fetchone()

    if not usuario:
        conn.execute(
            sa.text(
                "INSERT INTO usuarios ("
                "   clinica_id_FK, nombre, apellido_paterno, apellido_materno, "
                "   correo_electronico, hash_contrasena, rol_id_FK, estado, "
                "   intentos_fallidos, creado_en, actualizado_en"
                ") VALUES ("
                "   1, 'Super', 'Administrador', 'Vitalia', "
                "   :correo, :hash_pw, 1, 'activo', 0, NOW(), NOW()"
                ")"
            ),
            {
                "correo": SUPERADMIN_EMAIL,
                "hash_pw": SUPERADMIN_HASH,
            },
        )
    else:
        conn.execute(
            sa.text(
                "UPDATE usuarios SET "
                "   hash_contrasena = :hash_pw, "
                "   rol_id_FK = 1, "
                "   estado = 'activo', "
                "   actualizado_en = NOW() "
                "WHERE correo_electronico = :correo"
            ),
            {
                "correo": SUPERADMIN_EMAIL,
                "hash_pw": SUPERADMIN_HASH,
            },
        )


def downgrade() -> None:
    """Elimina el usuario SuperAdmin creado para el Backoffice."""
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM usuarios WHERE correo_electronico = :correo"),
        {"correo": SUPERADMIN_EMAIL},
    )
