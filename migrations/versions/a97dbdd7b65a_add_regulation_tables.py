"""add_regulation_tables

Revision ID: a97dbdd7b65a
Revises: bc7abe3eb83c
Create Date: 2022-06-14 11:05:40.543036

"""
from collections import namedtuple
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session

# revision identifiers, used by Alembic.
revision = "a97dbdd7b65a"
down_revision = "bc7abe3eb83c"
branch_labels = None
depends_on = None

RegulationCheckData = namedtuple(
    "RegulationCheckData",
    ["type", "label", "description", "regulation_rule", "variables"],
)


def fill_regulation_check():
    session = Session(bind=op.get_bind())
    regulation_check_data = [
        RegulationCheckData(
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            description="La durée du repos quotidien est d'au-moins 10h toutes les 24h (article R. 3312-53, 2° du code des transports)",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(
                    LONG_BREAK_DURATION_IN_HOURS=10,
                )
            ),
        ),
        RegulationCheckData(
            type="maximumWorkDayTime",
            label="Dépassement(s) de la durée maximale du travail quotidien",
            description="La durée du travail quotidien est limitée à 12h (article R. 3312-a51 du code des transports)",
            regulation_rule="dailyWork",
            variables=json.dumps(
                dict(
                    MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS=10,
                    MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS=12,
                    # START_DAY_WORK_HOUR=5,
                )
            ),
        ),
        RegulationCheckData(
            type="minimumWorkDayBreak",
            label="Non-respect(s) du temps de pause",
            description="Lorsque le temps de travail dépasse 6h le temps de pause minimal est de 30 minutes (article L3312-2 du code des transports). Lorsque le temps de travail dépasse 9h le temps de pause minimal passe à 45 minutes. Le temps de pause peut être réparti en périodes d'au-moins 15 minutes.",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(
                    MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN=15,
                    MINIMUM_DURATION_WORK_IN_HOURS_1=6,
                    MINIMUM_DURATION_WORK_IN_HOURS_2=9,
                    MINIMUM_DURATION_BREAK_IN_MIN_1=30,
                    MINIMUM_DURATION_BREAK_IN_MIN_2=45,
                )
            ),
        ),
        RegulationCheckData(
            type="maximumUninterruptedWorkTime",
            label="Dépassement(s) de la durée maximale du travail ininterrompu",
            description="Lorsque le temps de travail dépasse 6h il doit être interrompu par un temps de pause (article L3312-2 du code des transports)",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS=6)
            ),
        ),
        RegulationCheckData(
            type="maximumWorkedDaysInWeek",
            label="Non-respect(s) du repos hebdomadaire",
            description="Il est interdit de travailler plus de six jours dans la semaine (article L. 3132-1 du code du travail). Le repos hebdomadaire doit durer au minimum 34h (article L. 3132-2 du code du travail)",
            regulation_rule="weeklyRest",
            variables=json.dumps(dict()),
        ),
    ]
    for r in regulation_check_data:
        session.execute(
            sa.text(
                """
            INSERT INTO regulation_check(
              creation_time,
              type,
              label,
              description,
              date_application_start,
              regulation_rule,
              variables
            )
            VALUES
            (
              NOW(),
              :type,
              :label,
              :description,
              TIMESTAMP '2019-11-01',
              :regulation_rule,
              :variables
            )
            """
            ),
            dict(
                type=r.type,
                label=r.label,
                description=r.description,
                regulation_rule=r.regulation_rule,
                variables=r.variables,
            ),
        )


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

    fill_regulation_check()

    op.create_table(
        "regulation_day",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
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
        op.f("ix_regulation_day_regulation_check_id"),
        "regulation_day",
        ["regulation_check_id"],
        unique=False,
    )
    op.create_table(
        "regulation_week",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("week", sa.Date(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
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
            "week",
            "user_id",
            "regulation_check_id",
            "submitter_type",
            name="only_one_entry_per_user_week_check_and_submitter_type",
        ),
    )
    op.create_index(
        op.f("ix_regulation_week_regulation_check_id"),
        "regulation_week",
        ["regulation_check_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_regulation_week_regulation_check_id"),
        table_name="regulation_week",
    )
    op.drop_table("regulation_week")
    op.drop_index(
        op.f("ix_regulation_day_regulation_check_id"),
        table_name="regulation_day",
    )
    op.drop_table("regulation_day")
    op.drop_table("regulation_check")
