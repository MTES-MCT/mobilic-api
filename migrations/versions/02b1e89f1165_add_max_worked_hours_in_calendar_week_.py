"""add max worked hours in calendar week regulation check

Revision ID: 02b1e89f1165
Revises: 209c1d0a5cf9
Create Date: 2024-07-10 16:18:47.552132

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.helpers.regulations_utils import insert_regulation_check
from app.services.get_regulation_checks import (
    REGULATION_CHECK_MAXIMUM_WORK_IN_CALENDAR_WEEK,
)

# revision identifiers, used by Alembic.
revision = "02b1e89f1165"
down_revision = "209c1d0a5cf9"
branch_labels = None
depends_on = None


def fill_new_regulation_check():
    session = Session(bind=op.get_bind())
    insert_regulation_check(
        session=session,
        regulation_check_data=REGULATION_CHECK_MAXIMUM_WORK_IN_CALENDAR_WEEK,
    )


def upgrade():
    op.execute(
        "ALTER TABLE regulation_check DROP CONSTRAINT IF EXISTS regulationchecktype"
    )
    op.alter_column(
        "regulation_check",
        "type",
        type_=sa.Enum(
            "minimumDailyRest",
            "maximumWorkDayTime",
            "minimumWorkDayBreak",
            "maximumUninterruptedWorkTime",
            "maximumWorkedDaysInWeek",
            "noLic",
            "maximumWorkInCalendarWeek",
            name="regulationchecktype",
            native_enum=False,
        ),
        nullable=False,
    )
    fill_new_regulation_check()


def downgrade():
    op.execute(
        "DELETE FROM regulation_check WHERE type = 'maximumWorkInCalendarWeek'"
    )
    op.execute(
        "ALTER TABLE regulation_check DROP CONSTRAINT IF EXISTS regulationchecktype"
    )
    op.alter_column(
        "regulation_check",
        "type",
        type_=sa.Enum(
            "minimumDailyRest",
            "maximumWorkDayTime",
            "minimumWorkDayBreak",
            "maximumUninterruptedWorkTime",
            "maximumWorkedDaysInWeek",
            "noLic",
            name="regulationchecktype",
            native_enum=False,
        ),
        nullable=False,
    )
