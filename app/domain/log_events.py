from app import app


class EventLogError:
    pass


def get_response_if_event_should_not_be_logged(
    user, submitter, event_time, reception_time, event_history, **kwargs,
):
    if not submitter or not user or not event_time:
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

    event_param_dict = dict(
        event_time=event_time,
        submitter=submitter,
        company_id=submitter.company_id,
        user=user,
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
