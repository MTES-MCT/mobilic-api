from unittest.mock import MagicMock, patch
import datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.time import FR_TIMEZONE, from_tz
from app.models import Mission, LocationEntry, MissionEnd
from app.models.activity import ActivityType
from app.models.location_entry import LocationEntryType

DEFAULT_PASSWORD = "password123!"


class AuthenticatedUserContext:
    def __init__(self, user=None):
        self.mocked_authenticated_user = None
        self.mocked_token_verification = None
        if user:
            self.mocked_token_verification = patch(
                "app.helpers.authentication.verify_jwt_in_request",
                new=MagicMock(return_value=None),
            )
            self.mocked_authenticated_user = patch(
                "flask_jwt_extended.utils.get_current_user",
                new=MagicMock(return_value=user),
            )

    def __enter__(self):
        if self.mocked_authenticated_user:
            self.mocked_token_verification.__enter__()
            self.mocked_authenticated_user.__enter__()
        return self

    def __exit__(self, *args):
        if self.mocked_token_verification:
            self.mocked_authenticated_user.__exit__(*args)
            self.mocked_token_verification.__exit__(*args)


def get_date(how_many_days_ago):
    today = datetime.date.today()
    return today - datetime.timedelta(days=how_many_days_ago)


def get_time(how_many_days_ago, hour, minute=0, tz=FR_TIMEZONE):
    day = get_date(how_many_days_ago)
    return get_datetime_tz(day.year, day.month, day.day, hour, minute, tz)


def get_datetime_tz(year, month=1, day=1, hour=0, minutes=0, tz=FR_TIMEZONE):
    return from_tz(datetime.datetime(year, month, day, hour, minutes), tz)


def create_mission(
    name,
    company,
    time,
    submitter,
    vehicle,
    address=None,
    add_location_entry=False,
):
    mission = Mission(
        name=name,
        company=company,
        reception_time=time,
        submitter=submitter,
        vehicle=vehicle,
    )
    db.session.add(mission)
    if add_location_entry:
        location_entry = LocationEntry(
            _address=address.address,
            mission=mission,
            reception_time=datetime.datetime.now(),
            submitter=submitter,
            _company_known_address=address,
            type=LocationEntryType.MISSION_START_LOCATION,
            creation_time=datetime.datetime.now(),
        )
        location_entry.register_kilometer_reading(
            2500, datetime.datetime.now()
        )
        db.session.add(location_entry)
    return mission


# work_periods=[
#   [start_time_0, end_time_0],
#   ...,
#   [start_time_n, end_time_n]
# ]
def log_and_validate_mission(
    mission_name, work_periods, company, employee, vehicle, validate=True
):
    mission = create_mission(
        name=mission_name,
        company=company,
        time=work_periods[0][0],
        submitter=employee,
        vehicle=vehicle,
    )
    db.session.commit()

    with AuthenticatedUserContext(user=employee):
        for wp in work_periods:
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=wp[1],
                start_time=wp[0],
                end_time=wp[1],
            )
        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=work_periods[-1][1],
                user=employee,
                mission=mission,
            )
        )
        if validate:
            validate_mission(
                submitter=employee,
                mission=mission,
                for_user=employee,
            )
    return mission
