from datetime import datetime

from app import app


class EventLogError:
    pass


def check_whether_event_should_be_logged(
    submitter_id, event_time, event_history, **kwargs,
):
    reception_time = datetime.now()
    if not submitter_id or not event_time:
        raise ValueError("Event is missing some core params : will not log")

    if (
        event_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise ValueError(
            f"Event time is in the future by {event_time - reception_time} : will not log"
        )

    if "user_time" in kwargs and kwargs["user_time"] > event_time:
        raise ValueError(f"Start time is after event time : will not log")

    event_param_dict = dict(
        event_time=event_time, submitter_id=submitter_id, **kwargs,
    )

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
        raise ValueError("Event already logged, aborting")
