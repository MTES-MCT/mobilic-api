import json
from collections import namedtuple
import sqlalchemy as sa

DAY = 86400
HOUR = 3600
MINUTE = 60

ComputationResult = namedtuple(
    "ComputationResult", ["success", "extra"], defaults=(False, None)
)

Break = namedtuple("Break", ["start_time", "end_time"])


def insert_regulation_check(session, regulation_check_data):
    session.execute(
        sa.text(
            """
            INSERT INTO regulation_check(
              creation_time,
              type,
              label,
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
              TIMESTAMP '2019-11-01',
              :regulation_rule,
              :variables,
              :unit
            )
        """
        ),
        dict(
            type=regulation_check_data.type,
            label=regulation_check_data.label,
            regulation_rule=regulation_check_data.regulation_rule,
            variables=json.dumps(regulation_check_data.variables),
            unit=regulation_check_data.unit,
        ),
    )
