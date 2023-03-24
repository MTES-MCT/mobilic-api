"""add_relevant_regulation_alert_index

Revision ID: 930314f0ed57
Revises: 1b4a586db7d2
Create Date: 2023-03-24 17:14:07.127527

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "930314f0ed57"
down_revision = "1b4a586db7d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_regulatory_alert_user_day_submitter_type"),
        "regulatory_alert",
        ["user_id", "day", "submitter_type"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_regulatory_alert_user_day_submitter_type"),
        table_name="regulatory_alert",
    )
