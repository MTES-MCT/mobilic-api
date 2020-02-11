class EventLogError:
    pass


def get_response_if_event_should_not_be_logged(
    user,
    submitter,
    company,
    event_time,
    reception_time,
    event_history,
    **kwargs,
):
    if not submitter or not user or not company or not event_time:
        return EventLogError

    if event_time >= reception_time:
        return EventLogError

    event_param_dict = dict(
        event_time=event_time,
        submitter=submitter,
        company=company,
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
        return already_existing_logs_for_event[0]

    return None
