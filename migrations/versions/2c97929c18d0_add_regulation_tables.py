"""add_regulation_tables

Revision ID: 2c97929c18d0
Revises: b6d1707c5ba1
Create Date: 2022-07-12 15:13:46.326828

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session

import json

from app.helpers.regulations_utils import insert_regulation_check
from app.models.regulation_check import RegulationCheckType
from app.services.get_regulation_checks import get_regulation_checks

# revision identifiers, used by Alembic.
revision = "2c97929c18d0"
down_revision = "b6d1707c5ba1"
branch_labels = None
depends_on = None


def fill_regulation_checks():
    session = Session(bind=op.get_bind())
    regulation_check_data = get_regulation_checks()
    for r in regulation_check_data:
        if r.type == RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK:
            continue
        insert_regulation_check(session=session, regulation_check_data=r)


def upgrade():
    op.create_table(
        "regulation_check",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "minimumDailyRest",
                "maximumWorkDayTime",
                "minimumWorkDayBreak",
                "maximumUninterruptedWorkTime",
                "maximumWorkedDaysInWeek",
                name="regulationchecktype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.Enum(
                "day",
                "week",
                name="unittype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("date_application_start", sa.Date(), nullable=False),
        sa.Column("date_application_end", sa.Date(), nullable=True),
        sa.Column(
            "regulation_rule",
            sa.Enum(
                "dailyWork",
                "dailyRest",
                "weeklyWork",
                "weeklyRest",
                name="regulationrule",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "variables",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    fill_regulation_checks()

    op.create_table(
        "regulatory_alert",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "extra",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "submitter_type",
            sa.Enum(
                "employee", "admin", name="submittertype", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("regulation_check_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["regulation_check_id"],
            ["regulation_check.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "day",
            "user_id",
            "regulation_check_id",
            "submitter_type",
            name="only_one_entry_per_user_day_check_and_submitter_type",
        ),
    )
    op.create_index(
        op.f("ix_regulatory_alert_regulation_check_id"),
        "regulatory_alert",
        ["regulation_check_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_regulatory_alert_regulation_check_id"),
        table_name="regulatory_alert",
    )
    op.drop_table("regulatory_alert")
    op.drop_table("regulation_check")
