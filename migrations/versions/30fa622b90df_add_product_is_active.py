"""Add product is_active

Revision ID: 30fa622b90df
Revises: 46058affdbe2
Create Date: 2026-02-15 18:59:27.705056
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '30fa622b90df'
down_revision = '46058affdbe2'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna con default para filas existentes
    with op.batch_alter_table("product") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true()
            )
        )

    # Quitar default después (opcional pero limpio)
    with op.batch_alter_table("product") as batch_op:
        batch_op.alter_column("is_active", server_default=None)


def downgrade():
    with op.batch_alter_table("product") as batch_op:
        batch_op.drop_column("is_active")
