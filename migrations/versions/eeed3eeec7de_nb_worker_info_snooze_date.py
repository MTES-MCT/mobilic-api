"""nb worker info snooze date

Revision ID: eeed3eeec7de
Revises: 68ed4db9ae15
Create Date: 2025-08-06 13:20:22.740531

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "eeed3eeec7de"
down_revision = "68ed4db9ae15"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employment",
        sa.Column("nb_worker_info_snooze_date", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("employment", "nb_worker_info_snooze_date")
