"""add company certificate badge request counter

Revision ID: bde869cbd775
Revises: 022d979043d0
Create Date: 2025-09-04 11:29:04.301143

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bde869cbd775"
down_revision = "022d979043d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company",
        sa.Column(
            "nb_certificate_badge_request",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade():
    op.drop_column("company", "nb_certificate_badge_request")
