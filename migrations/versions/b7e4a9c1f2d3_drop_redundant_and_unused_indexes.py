"""drop_redundant_and_unused_indexes

Drop indexes flagged by the index audit (Trello b5VCvVo3):
- 5 single-column FK indexes redundant with a composite constraint index
  whose leading column is the same (index=True also removed from the models)
- ix_totp_credential_owner: duplicate of uq_totp_credential_owner
- idx_activity_gin: unused GIN index (no code usage, 299 MB)

All operations run CONCURRENTLY so they never block reads/writes in prod.

Revision ID: b7e4a9c1f2d3
Revises: 0da0a33704b0
Create Date: 2026-07-21 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7e4a9c1f2d3"
down_revision = "0da0a33704b0"
branch_labels = None
depends_on = None


INDEXES = [
    (
        "ix_location_entry_mission_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_location_entry_mission_id "
        "ON location_entry (mission_id)",
    ),
    (
        "ix_user_agreement_user_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_user_agreement_user_id "
        "ON user_agreement (user_id)",
    ),
    (
        "ix_vehicle_company_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_vehicle_company_id "
        "ON vehicle (company_id)",
    ),
    (
        "ix_mission_auto_validation_user_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_mission_auto_validation_user_id "
        "ON mission_auto_validation (user_id)",
    ),
    (
        "ix_company_known_address_company_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_company_known_address_company_id "
        "ON company_known_address (company_id)",
    ),
    (
        "ix_totp_credential_owner",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_totp_credential_owner "
        "ON totp_credential (owner_type, owner_id)",
    ),
    (
        "idx_activity_gin",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_gin "
        "ON activity USING gin ((ARRAY[user_id, submitter_id, "
        "dismiss_author_id])) WITH (fastupdate='on')",
    ),
]


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    for name, _ in INDEXES:
        conn.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {name}"))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    for _, recreate in INDEXES:
        conn.execute(sa.text(recreate))
