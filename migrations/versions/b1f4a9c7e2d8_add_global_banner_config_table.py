"""add global_banner_config table

Revision ID: b1f4a9c7e2d8
Revises: e7a3c9d1b2f4
Create Date: 2026-10-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1f4a9c7e2d8"
down_revision = "e7a3c9d1b2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "global_banner_config",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "info",
                "warning",
                "error",
                name="globalbannerlevel",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("global_banner_config")
