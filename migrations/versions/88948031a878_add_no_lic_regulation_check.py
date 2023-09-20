"""add No LIC regulation check

Revision ID: 88948031a878
Revises: 91a93a56a303
Create Date: 2023-08-10 12:12:27.357582

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.regulation_check import UnitType, RegulationCheckType

# revision identifiers, used by Alembic.
revision = "88948031a878"
down_revision = "91a93a56a303"
branch_labels = None
depends_on = None


def fill_new_regulation_check():
    session = Session(bind=op.get_bind())
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
          variables,
          unit
        )
        VALUES
        (
          NOW(),
          :type,
          :label,
          :description,
          TIMESTAMP '2019-11-01',
          :regulation_rule,
          :variables,
          :unit
        )
        """
        ),
        dict(
            type=RegulationCheckType.NO_LIC,
            label="Absence de livret individuel de contrôle à bord",
            description="Défaut de documents nécessaires au décompte de la durée du travail (L. 3121-67 du Code du travail et R. 3312‑58 du Code des transports + arrêté du 20 juillet 1998)",
            regulation_rule=None,
            variables=None,
            unit=UnitType.DAY,
        ),
    )


def upgrade():
    op.execute(
        "ALTER TABLE regulation_check ALTER COLUMN regulation_rule DROP NOT NULL"
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
    fill_new_regulation_check()


def downgrade():
    op.execute("DELETE FROM regulation_check WHERE type = 'noLic'")
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
            name="regulationchecktype",
            native_enum=False,
        ),
        nullable=False,
    )
    op.execute(
        "ALTER TABLE regulation_check ALTER COLUMN regulation_rule SET NOT NULL"
    )
