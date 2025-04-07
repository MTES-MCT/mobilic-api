"""add regulation check work day break

Revision ID: 60f5c0616731
Revises: 15fc3b5f23c4
Create Date: 2025-04-07 16:52:54.637928

"""
from datetime import date

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.helpers.regulations_utils import insert_regulation_check
from app.models import RegulatoryAlert, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.services.get_regulation_checks import REGULATION_CHECK_ENOUGH_BREAK

# revision identifiers, used by Alembic.
revision = "60f5c0616731"
down_revision = "15fc3b5f23c4"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    session = Session(bind=conn)

    # Add regulation check type constraint
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
            "enoughBreak",
            name="regulationchecktype",
            native_enum=False,
        ),
        nullable=False,
    )

    insert_regulation_check(
        session=session,
        regulation_check_data=REGULATION_CHECK_ENOUGH_BREAK,
        timestamp=date.today().isoformat(),
    )

    for check_type in [
        RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME,
        RegulationCheckType.MINIMUM_WORK_DAY_BREAK,
    ]:
        check = (
            session.query(RegulationCheck).filter_by(type=check_type).first()
        )
        if check:
            check.date_application_end = date.today()

    session.commit()


def downgrade():
    pass
