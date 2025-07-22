"""add late registration justification in mission

Revision ID: d20f73ecb9fc
Revises: 2403c7f1843d
Create Date: 2025-07-11 10:34:41.244352

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d20f73ecb9fc"
down_revision = "2403c7f1843d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mission",
        sa.Column(
            "past_registration_justification",
            sa.String(length=48),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("mission", "past_registration_justification")
