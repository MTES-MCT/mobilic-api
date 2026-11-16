"""migrate tachograph holiday activities from off to work

Revision ID: 4402ca8e8bd4
Revises: b1f4a9c7e2d8
Create Date: 2026-11-12 13:00:43.123484

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4402ca8e8bd4"
down_revision = "b1f4a9c7e2d8"
branch_labels = None
depends_on = None


def upgrade():
    # "Activités tachygraphe" periods were logged as OFF holiday activities;
    # they are actual work and must count as worked time, not rest. Flip their
    # activity type to WORK. The mission keeps its name, so it is identifiable;
    # activity_version.type is a property deriving from activity.type, so the
    # history follows. Regulations must be recomputed for the affected users
    # afterwards (flask init_regulation_alerts), not in this migration.
    op.execute(
        sa.text(
            """
            UPDATE activity
            SET type = 'work'
            WHERE type = 'off'
              AND mission_id IN (
                  SELECT id FROM mission
                  WHERE name = 'Activités tachygraphe'
              )
            """
        )
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE activity
            SET type = 'off'
            WHERE type = 'work'
              AND mission_id IN (
                  SELECT id FROM mission
                  WHERE name = 'Activités tachygraphe'
              )
            """
        )
    )
