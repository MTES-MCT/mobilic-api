"""add_support_action_log

Revision ID: ed3f60d26a7a
Revises: 584e53171959
Create Date: 2026-03-19 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "ed3f60d26a7a"
down_revision = "584e53171959"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_action_log",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "creation_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "support_user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "impersonated_user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column(
            "old_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "new_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_support_action_log_support_user_id",
        "support_action_log",
        ["support_user_id"],
    )
    op.create_index(
        "ix_support_action_log_impersonated_user_id",
        "support_action_log",
        ["impersonated_user_id"],
    )
    op.create_index(
        "ix_support_action_log_creation_time",
        "support_action_log",
        ["creation_time"],
    )


def downgrade():
    op.drop_index(
        "ix_support_action_log_creation_time",
        "support_action_log",
    )
    op.drop_index(
        "ix_support_action_log_impersonated_user_id",
        "support_action_log",
    )
    op.drop_index(
        "ix_support_action_log_support_user_id",
        "support_action_log",
    )
    op.drop_table("support_action_log")
