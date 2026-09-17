"""add sent_to_driver column

Revision ID: e6015df7d17e
Revises: c8f1a2b3d4e5
Create Date: 2026-08-20 11:29:03.357344

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e6015df7d17e"
down_revision = "c8f1a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("sent_to_driver", sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column("controller_control", "sent_to_driver")
