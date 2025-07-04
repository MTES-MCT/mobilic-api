"""add_notification_table

Revision ID: 4ebd50b0ef82
Revises: fe1e80dc69fe
Create Date: 2025-06-23 13:58:14.117678

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4ebd50b0ef82"
down_revision = "fe1e80dc69fe"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification",
        sa.Column(
            "type",
            sa.Enum(
                "mission_changes_warning",
                "mission_auto_validation",
                "new_mission_by_admin",
                name="notificationtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "data",
            sa.dialects.postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_creation_time"),
        "notification",
        ["creation_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_user_id"),
        "notification",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_notification_user_id"), table_name="notification")
    op.drop_index(
        op.f("ix_notification_creation_time"), table_name="notification"
    )
    op.drop_table("notification")
