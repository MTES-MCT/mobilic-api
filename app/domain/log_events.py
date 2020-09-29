from app import app
from app.helpers.errors import InvalidParamsError


def check_whether_event_should_be_logged(
    submitter_id, reception_time, event_time
):
    if not submitter_id:
        raise InvalidParamsError(
            "Event is missing some core params : it will not be logged"
        )

    if (
        event_time
        and event_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise InvalidParamsError(
            f"Event time is in the future by {event_time - reception_time} : it will not be logged"
        )
