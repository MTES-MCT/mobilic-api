from app.models.controller_control import ControllerControl

CONTROL_API_QUERY_NAMES = ["controlData", "readMissionControlData"]


def retrieve_max_reception_time(info):
    if info.path[0] in CONTROL_API_QUERY_NAMES:
        controller_control = ControllerControl.query.get(
            info.variable_values["controlId"]
        )
        return controller_control.qr_code_generation_time
    return None
