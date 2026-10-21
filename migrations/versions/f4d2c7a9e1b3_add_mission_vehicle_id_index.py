"""add_missing_fk_indexes_anonymization

Revision ID: f4d2c7a9e1b3
Revises: e7a3c9d1b2f4
Create Date: 2026-10-21 11:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f4d2c7a9e1b3"
down_revision = "e7a3c9d1b2f4"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_mission_vehicle_id", "mission", "vehicle_id"),
    (
        "ix_location_entry_company_known_address_id",
        "location_entry",
        "company_known_address_id",
    ),
    ("ix_activity_last_submitter_id", "activity", "last_submitter_id"),
]


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    for name, table, column in INDEXES:
        conn.execute(
            sa.text(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
                f"ON {table} ({column})"
            )
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    for name, _table, _column in INDEXES:
        conn.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {name}"))
