from datetime import datetime

from app import app
from app.helpers.errors import InvalidParamsError, EventAlreadyLoggedError


def check_whether_event_should_be_logged(
    submitter_id,
    reception_time,
    event_history,
    relevant_time_name=None,
    **kwargs,
):
    if not submitter_id:
        raise InvalidParamsError(
            "Event is missing some core params : will not log"
        )

    relevant_time = None
    if relevant_time_name:
        relevant_time = kwargs.get(relevant_time_name)

    if (
        relevant_time
        and relevant_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise InvalidParamsError(
            f"Event time is in the future by {relevant_time - reception_time} : will not log"
        )

    event_param_dict = dict(submitter_id=submitter_id, **kwargs,)

    already_existing_logs_for_event = [
        event
        for event in event_history
        if all(
            [
                getattr(event, param_name) == param_value
                for param_name, param_value in event_param_dict.items()
            ]
        )
    ]

    if len(already_existing_logs_for_event) > 0:
        raise EventAlreadyLoggedError("Event already logged, aborting")
