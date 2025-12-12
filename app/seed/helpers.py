from unittest.mock import MagicMock, patch
import datetime

from faker import Faker

from app import db
from app.domain.expenditure import log_expenditure
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.time import FR_TIMEZONE, from_tz
from app.models import (
    Mission,
    LocationEntry,
    MissionEnd,
    MissionValidation,
    Vehicle,
    CompanyKnownAddress,
    Address,
    Comment,
)
from app.models.activity import ActivityType
from app.models.location_entry import LocationEntryType
from app.seed.factories import EmploymentFactory, UserFactory

DEFAULT_PASSWORD = "password123!"
fake = Faker("fr_FR")


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
    vehicle=None,
    address=None,
    add_location_entry=False,
):
    mission = Mission(
        name=name,
        company=company,
        reception_time=time,
        creation_time=time,
        submitter=submitter,
        vehicle=vehicle,
    )
    db.session.add(mission)
    db.session.flush()
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
        if vehicle is not None:
            location_entry.register_kilometer_reading(
                2500, datetime.datetime.now()
            )
        db.session.add(location_entry)
    return mission


def end_mission(
    mission, submitter, for_user, time, address=None, add_location_entry=False
):
    db.session.add(
        MissionEnd(
            submitter=submitter,
            reception_time=time,
            user=for_user,
            mission=mission,
        )
    )
    if add_location_entry:
        location_entry = LocationEntry(
            _address=address.address,
            mission=mission,
            reception_time=time,
            submitter=submitter,
            _company_known_address=address,
            type=LocationEntryType.MISSION_END_LOCATION,
            creation_time=time,
        )
        db.session.add(location_entry)


# work_periods=[
#   [start_time_0, end_time_0],
#   ...,
#   [start_time_n, end_time_n]
# ]
def log_and_validate_mission(
    mission_name,
    work_periods,
    company,
    employee,
    vehicle=None,
    validate=True,
    admin_validating=None,
    address=None,
    add_location_entry=False,
    employee_expenditure=None,
    employee_comment=None,
):
    if not vehicle and company.vehicles:
        vehicle = company.vehicles[0]
    mission = create_mission(
        name=mission_name,
        company=company,
        time=work_periods[0][0],
        submitter=employee,
        vehicle=vehicle,
        add_location_entry=add_location_entry,
        address=address,
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
                creation_time=wp[0],
                start_time=wp[0],
                end_time=wp[1],
            )
        if employee_expenditure:
            log_expenditure(
                submitter=employee,
                user=employee,
                mission=mission,
                type=employee_expenditure,
                reception_time=work_periods[-1][1],
                spending_date=work_periods[-1][1].date(),
                creation_time=work_periods[-1][1],
            )
        if employee_comment:
            db.session.add(
                Comment(
                    submitter=employee,
                    mission=mission,
                    text=employee_comment,
                    reception_time=work_periods[-1][1],
                )
            )
        end_mission(
            mission=mission,
            submitter=employee,
            for_user=employee,
            time=work_periods[-1][1],
            add_location_entry=add_location_entry,
            address=address,
        )
        if validate:
            validate_mission(
                submitter=employee,
                mission=mission,
                for_user=employee,
                creation_time=work_periods[-1][1],
            )
    if admin_validating is not None:
        validate_mission(
            mission=mission,
            is_admin_validation=True,
            for_user=employee,
            submitter=admin_validating,
            creation_time=work_periods[-1][1] + datetime.timedelta(days=1),
        )

    return mission


def add_employee(company, admin, email="", first_name="", last_name=""):
    if first_name == "" and last_name == "":
        first_name = fake.first_name()
        last_name = fake.last_name()

    if email == "":
        email = f"{first_name.lower()}.{last_name.lower()}@employee.com"

    employee = UserFactory.create(
        email=email,
        password=DEFAULT_PASSWORD,
        first_name=first_name,
        last_name=last_name,
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )
    return employee


def create_vehicle(company):
    vehicle = Vehicle(
        registration_number=fake.license_plate(),
        alias=fake.word(),
        company_id=company.id,
    )
    db.session.add(vehicle)
    return vehicle


def create_address(company):
    address = CompanyKnownAddress(
        alias=fake.company(),
        address=Address.get_or_create(
            geo_api_data=None, manual_address=fake.address()
        ),
        company_id=company.id,
    )
    db.session.add(address)
    return address
