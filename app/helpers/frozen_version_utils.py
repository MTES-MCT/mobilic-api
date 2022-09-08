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
