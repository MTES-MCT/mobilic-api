def freeze_activities(
    activities,
    freeze_time,
    include_dismissed_activities=False,
    include_posteriori_activities=False,
):
    frozen_activities = list(
        map(
            lambda a: a.freeze_activity_at(
                freeze_time,
                include_dismissed_activities,
                include_posteriori_activities,
            ),
            activities,
        )
    )
    return list(filter(lambda item: item is not None, frozen_activities))


def filter_out_future_events(events, max_reception_time):
    return list(
        filter(
            lambda event: event.reception_time <= max_reception_time,
            iter(events),
        )
    )
