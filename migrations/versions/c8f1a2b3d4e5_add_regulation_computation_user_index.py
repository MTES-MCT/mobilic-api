"""add_regulation_computation_user_index

Add ix_regulation_computation_user_submitter_day (user_id, submitter_type,
day) to serve the admin activity tab query (user_id IN (...) AND
submitter_type = 'admin' AND day BETWEEN ...). The existing unique index has
day as leading column, so user_id could not be seeked (Trello b5VCvVo3).

Revision ID: c8f1a2b3d4e5
Revises: b7e4a9c1f2d3
Create Date: 2026-07-21 12:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c8f1a2b3d4e5"
down_revision = "b7e4a9c1f2d3"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(
        sa.text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_regulation_computation_user_submitter_day "
            "ON regulation_computation (user_id, submitter_type, day)"
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(
        sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_regulation_computation_user_submitter_day"
        )
    )
