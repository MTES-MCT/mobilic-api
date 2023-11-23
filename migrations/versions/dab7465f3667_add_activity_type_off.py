"""add activity type OFF

Revision ID: dab7465f3667
Revises: 2179a955a24d
Create Date: 2023-11-06 12:20:22.069685

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import ActivityVersion, Activity

# revision identifiers, used by Alembic.
revision = "dab7465f3667"
down_revision = "2179a955a24d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE activity DROP CONSTRAINT IF EXISTS activitytypes")
    op.alter_column(
        "activity",
        "type",
        type_=sa.Enum(
            "drive",
            "support",
            "work",
            "transfer",
            "off",
            name="activitytypes",
            native_enum=False,
        ),
    )


def downgrade():
    session = Session(bind=op.get_bind())

    activity_ids = [
        res[0]
        for res in session.execute(
            """
        SELECT id
        FROM activity
        WHERE type = 'off'
        """
        ).fetchall()
    ]

    if activity_ids:
        session.query(ActivityVersion).filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)
        session.query(Activity).filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )

    op.execute("ALTER TABLE activity DROP CONSTRAINT IF EXISTS activitytypes")
    op.alter_column(
        "activity",
        "type",
        type_=sa.Enum(
            "drive",
            "support",
            "work",
            "transfer",
            name="activitytypes",
            native_enum=False,
        ),
    )
