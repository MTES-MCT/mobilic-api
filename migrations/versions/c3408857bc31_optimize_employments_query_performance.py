"""optimize_employments_query_performance

Revision ID: c3408857bc31
Revises: de1be8351df4
Create Date: 2026-02-18 13:59:28.478688

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3408857bc31"
down_revision = "de1be8351df4"
branch_labels = None
depends_on = None


def upgrade():
    # Add composite index to optimize latestPerUser query
    # CONCURRENTLY: Index creation without blocking INSERT/UPDATE/DELETE
    # This is safer for production but takes longer to complete
    # Must commit the current transaction before CONCURRENTLY operations
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))

    conn.execute(
        sa.text(
            """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_employment_latest_per_user
        ON employment (
            user_id,
            (CASE WHEN end_date IS NULL THEN 0 ELSE 1 END),
            start_date DESC,
            id DESC
        )
        WHERE dismissed_at IS NULL AND validation_status != 'rejected'
        """
        )
    )

    # Add composite index for base filters used in resolve_employments
    conn.execute(
        sa.text(
            """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_employment_company_active
        ON employment (company_id, validation_status)
        WHERE dismissed_at IS NULL
        """
        )
    )

    # Optimize the trigger function to reduce overhead
    # The original function is kept as-is, we only ensure it's properly set up
    # The real optimization comes from the indexes above
    op.execute(
        """
    CREATE OR REPLACE FUNCTION insert_last_active_at()
    RETURNS TRIGGER AS $$
    DECLARE
        mission_end_time TIMESTAMP;
    BEGIN
        -- Only proceed if the mission actually has activities
        SELECT MAX(a.end_time) INTO mission_end_time
        FROM activity a
        WHERE a.mission_id = NEW.mission_id
        AND a.user_id = NEW.user_id
        AND a.dismissed_at IS NULL
        AND a.end_time IS NOT NULL;

        -- Only update if we found a valid end time
        IF mission_end_time IS NOT NULL THEN
            UPDATE employment e
            SET last_active_at = mission_end_time
            FROM mission m
            WHERE m.id = NEW.mission_id
            AND e.user_id = NEW.user_id
            AND e.validation_status = 'approved'
            AND e.company_id = m.company_id
            AND e.end_date IS NULL
            AND e.dismissed_at IS NULL
            AND (e.last_active_at IS NULL OR e.last_active_at < mission_end_time);
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    )


def downgrade():
    # Remove the indexes (CONCURRENTLY for safe removal)
    # Must commit the current transaction before CONCURRENTLY operations
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))

    conn.execute(
        sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_employment_latest_per_user"
        )
    )
    conn.execute(
        sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_employment_company_active"
        )
    )

    # Restore the original trigger function (without the EXISTS optimization)
    op.execute(
        """
    CREATE OR REPLACE FUNCTION insert_last_active_at()
    RETURNS TRIGGER AS $$
    DECLARE
        mission_end_time TIMESTAMP;
    BEGIN
        SELECT MAX(a.end_time) INTO mission_end_time
        FROM activity a
        WHERE a.mission_id = NEW.mission_id
        AND a.user_id = NEW.user_id
        AND a.dismissed_at IS NULL
        AND a.end_time IS NOT NULL;

        IF mission_end_time IS NOT NULL THEN
            UPDATE employment e
            SET last_active_at = mission_end_time
            FROM mission m
            WHERE m.id = NEW.mission_id
            AND e.user_id = NEW.user_id
            AND e.validation_status = 'approved'
            AND e.company_id = m.company_id
            AND e.end_date IS NULL
            AND e.dismissed_at IS NULL
            AND (e.last_active_at < mission_end_time OR e.last_active_at IS NULL);
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    )
