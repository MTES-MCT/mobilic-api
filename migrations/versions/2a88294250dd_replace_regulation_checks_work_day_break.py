"""replace regulation checks work day break

Revision ID: 2a88294250dd
Revises: 15fc3b5f23c4
Create Date: 2025-04-03 11:28:39.996003

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.helpers.regulations_utils import insert_regulation_check
from app.models import RegulatoryAlert, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.services.get_regulation_checks import REGULATION_CHECK_ENOUGH_BREAK

# revision identifiers, used by Alembic.
revision = "2a88294250dd"
down_revision = "15fc3b5f23c4"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    session = Session(bind=conn)

    # Delete two legacy regulation checks and the regulatory alerts associated
    regulation_check_ids_to_delete = (
        session.query(RegulationCheck.id)
        .filter(
            RegulationCheck.type.in_(
                [
                    RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME,
                    RegulationCheckType.MINIMUM_WORK_DAY_BREAK,
                ]
            )
        )
        .all()
    )
    regulation_check_ids_to_delete = [
        rc[0] for rc in regulation_check_ids_to_delete
    ]

    if regulation_check_ids_to_delete:
        session.query(RegulatoryAlert).filter(
            RegulatoryAlert.regulation_check_id.in_(
                regulation_check_ids_to_delete
            )
        ).delete(synchronize_session=False)

        session.query(RegulationCheck).filter(
            RegulationCheck.id.in_(regulation_check_ids_to_delete)
        ).delete(synchronize_session=False)

    session.commit()

    # Update regulation check type constraint
    op.execute(
        "ALTER TABLE regulation_check DROP CONSTRAINT IF EXISTS regulationchecktype"
    )
    op.alter_column(
        "regulation_check",
        "type",
        type_=sa.Enum(
            "minimumDailyRest",
            "maximumWorkDayTime",
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
    )


def downgrade():
    pass
