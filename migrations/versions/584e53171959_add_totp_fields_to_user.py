"""add_totp_credential_table

Revision ID: 584e53171959
Revises: f8a1b2c3d4e5
Create Date: 2026-03-17 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "584e53171959"
down_revision = "f8a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "totp_credential",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "creation_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("owner_type", sa.String(50), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("secret", sa.String(255), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            name="uq_totp_credential_owner",
        ),
    )
    op.create_index(
        "ix_totp_credential_owner",
        "totp_credential",
        ["owner_type", "owner_id"],
    )


def downgrade():
    op.drop_index("ix_totp_credential_owner", "totp_credential")
    op.drop_table("totp_credential")
