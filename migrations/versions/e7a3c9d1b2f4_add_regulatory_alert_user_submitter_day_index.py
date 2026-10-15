"""add regulatory_alert (user_id, submitter_type, day) index

Revision ID: e7a3c9d1b2f4
Revises: 4ca13e06a9b5
Create Date: 2026-09-23 18:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7a3c9d1b2f4"
down_revision = "4ca13e06a9b5"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(
        sa.text(
            """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_regulatory_alert_user_submitter_day
        ON regulatory_alert (user_id, submitter_type, day)
        """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(
        sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_regulatory_alert_user_submitter_day"
        )
    )
