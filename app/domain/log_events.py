from datetime import datetime

from app import app


class EventLogError:
    pass


def check_whether_event_should_not_be_logged(
    submitter, event_time, event_history, **kwargs,
):
    reception_time = datetime.now()
    if not submitter or not event_time:
        app.logger.warn("Event is missing some core params : will not log")
        return EventLogError

    if (
        event_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        app.logger.warn(
            f"Event time is in the future by {event_time - reception_time} : will not log"
        )
        return EventLogError

    if "start_time" in kwargs and kwargs["start_time"] > event_time:
        app.logger.warn(f"Start time is after event time : will not log")
        return EventLogError

    event_param_dict = dict(
        event_time=event_time,
        submitter=submitter,
        company_id=submitter.company_id,
        **kwargs,
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
        app.logger.info("Event already logged, aborting")
        return already_existing_logs_for_event[0]

    return None
