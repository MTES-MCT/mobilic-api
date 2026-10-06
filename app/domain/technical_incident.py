from app import db
from app.helpers.errors import InvalidParamsError
from app.models.technical_incident import TechnicalIncident

MAX_DESCRIPTION_LENGTH = 2000

# Sentinel distinguishing "field not provided" from an explicit None (e.g.
# clearing end_time to reopen an incident).
_UNSET = object()


def validate_period(start_time, end_time):
    if end_time is not None and end_time < start_time:
        raise InvalidParamsError(
            "La date de fin doit être postérieure à la date de début"
        )


def clean_description(description):
    description = (description or "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise InvalidParamsError(
            f"La description ne doit pas dépasser {MAX_DESCRIPTION_LENGTH} "
            "caractères"
        )
    return description or None


def create_incident(
    technical_type, start_time, end_time=None, description=None
):
    validate_period(start_time, end_time)
    incident = TechnicalIncident(
        technical_type=technical_type,
        start_time=start_time,
        end_time=end_time,
        description=clean_description(description),
    )
    db.session.add(incident)
    return incident


def update_incident(
    incident,
    technical_type=_UNSET,
    start_time=_UNSET,
    end_time=_UNSET,
    description=_UNSET,
):
    new_start = start_time if start_time is not _UNSET else incident.start_time
    new_end = end_time if end_time is not _UNSET else incident.end_time
    validate_period(new_start, new_end)

    if technical_type is not _UNSET:
        incident.technical_type = technical_type
    if start_time is not _UNSET:
        incident.start_time = start_time
    if end_time is not _UNSET:
        incident.end_time = end_time
    if description is not _UNSET:
        incident.description = clean_description(description)
    return incident
