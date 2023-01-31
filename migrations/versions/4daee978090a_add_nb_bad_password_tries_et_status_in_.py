"""add nb_bad_password_tries et status in user table

Revision ID: 4daee978090a
Revises: e0834912bc9c
Create Date: 2023-01-26 16:53:19.335083

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4daee978090a"
down_revision = "e0834912bc9c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("nb_bad_password_tries", sa.Integer()))
    op.add_column(
        "user",
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "blocked_bad_password",
                "third_party_pending_approval",
                name="useraccountstatus",
                native_enum=False,
            ),
        ),
    )
    op.execute(
        """UPDATE \"user\" SET nb_bad_password_tries = 0, status = 'active'"""
    )
    op.alter_column("user", "nb_bad_password_tries", nullable=False)
    op.alter_column("user", "status", nullable=False)


def downgrade():
    op.drop_column("user", "status")
    op.drop_column("user", "nb_bad_password_tries")
