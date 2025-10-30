"""add exports table

Revision ID: c1e0cfacea5a
Revises: 20b56cbd2d05
Create Date: 2025-10-28 17:21:23.525128

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1e0cfacea5a"
down_revision = "20b56cbd2d05"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "export",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("file_s3_path", sa.String(), nullable=True),
        sa.Column("file_type", sa.String(), nullable=True),
        sa.Column(
            "export_type",
            sa.Enum("excel", name="exporttype", native_enum=False),
            server_default="excel",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "work_in_progress",
                "ready",
                "downloaded",
                "cancelled",
                "failed",
                name="exportstatus",
                native_enum=False,
            ),
            server_default="work_in_progress",
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_export_user_id"), "export", ["user_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_export_user_id"), table_name="export")
    op.drop_table("export")
