from datetime import datetime

from sqlalchemy import extract

from app.models import ScenarioTesting


def get_scenario_testing_query_for_user_this_month(user_id):
    current_month = datetime.now().month
    return ScenarioTesting.query.filter(
        ScenarioTesting.user_id == user_id,
        extract("month", ScenarioTesting.creation_time) == current_month,
    )


def check_scenario_testing_action_already_exists_this_month(
    user_id, action, scenario
):
    existing_action_result = (
        get_scenario_testing_query_for_user_this_month(user_id=user_id)
        .filter(
            ScenarioTesting.action == action,
            ScenarioTesting.scenario == scenario,
        )
        .first()
    )
    return existing_action_result is not None
