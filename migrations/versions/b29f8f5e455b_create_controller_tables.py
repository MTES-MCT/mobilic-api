"""create controller tables

Revision ID: b29f8f5e455b
Revises: 420dbfec0b28
Create Date: 2022-07-12 11:55:45.368316

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b29f8f5e455b"
down_revision = "420dbfec0b28"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controller_user",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("agent_connect_id", sa.String(length=255), nullable=False),
        sa.Column(
            "agent_connect_info",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "organizational_unit", sa.String(length=255), nullable=False
        ),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_connect_id"),
        sa.UniqueConstraint("organizational_unit"),
    )
    op.create_table(
        "controller_refresh_token",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("controller_user_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["controller_user_id"],
            ["controller_user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_controller_refresh_token_controller_user_id"),
        "controller_refresh_token",
        ["controller_user_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_index(
        op.f("ix_controller_refresh_token_controller_user_id"),
        table_name="controller_refresh_token",
    )
    op.drop_table("controller_refresh_token")
    op.drop_table("controller_user")
    # ### end Alembic commands ###
