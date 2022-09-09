from app.models.controller_control import ControllerControl


def retrieve_max_reception_time(info):
    # TODO à discuter en review
    # if info.context.view_args["max_reception_time"]:
    if (
        info.path[0] == "controlData"
        or info.path[0] == "readMissionControlData"
    ):
        controller_control = ControllerControl.query.get(
            info.variable_values["controlId"]
        )
        return controller_control.qr_code_generation_time
    return None


def freeze_activities(activities, freeze_time):
    frozen_activities = list(
        map(
            lambda a: a.freeze_activity_at(freeze_time),
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
