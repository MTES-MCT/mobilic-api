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


def insert_regulation_check(
    session,
    regulation_check_data,
    start_timestamp="2019-11-01",
    end_timestamp=None,
):

    base_query = """
            INSERT INTO regulation_check(
              creation_time,
              type,
              label,
              date_application_start,
              {end_field}
              regulation_rule,
              variables,
              unit
            )
            VALUES
            (
              NOW(),
              :type,
              :label,
              TIMESTAMP :start_timestamp,
              {end_value}
              :regulation_rule,
              :variables,
              :unit
            )
        """

    params = dict(
        type=regulation_check_data.type,
        label=regulation_check_data.label,
        regulation_rule=regulation_check_data.regulation_rule,
        variables=json.dumps(regulation_check_data.variables),
        unit=regulation_check_data.unit,
        start_timestamp=start_timestamp,
    )

    if end_timestamp is not None:
        query = base_query.format(
            end_field="date_application_end,",
            end_value="TIMESTAMP :end_timestamp,",
        )
        params["end_timestamp"] = end_timestamp
    else:
        query = base_query.format(end_field="", end_value="")

    session.execute(sa.text(query), params)
