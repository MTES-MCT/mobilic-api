from datetime import time, datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import (
    Vehicle,
    CompanyKnownAddress,
    Address,
    Mission,
    MissionEnd,
    LocationEntry,
)
from app.models.activity import ActivityType
from app.models.location_entry import LocationEntryType
from app.seed import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.helpers import AuthenticatedUserContext, DEFAULT_PASSWORD

ADMIN_EMAIL = "export_excel@admin.com"
EMPLOYEE_1_EMAIL = "export_excel1@employee.com"
EMPLOYEE_2_EMAIL = "export_excel2@employee.com"
EMPLOYEE_3_EMAIL = "export_excel3@employee.com"
EMPLOYEE_4_EMAIL = "export_excel4@employee.com"
A_FRENCH_HOLIDAY = datetime(2025, 4, 21)
A_SUNDAY = datetime(2025, 4, 13)
DAY_MULTIPLE_MISSIONS = datetime(2025, 4, 23)
DAY_MISSION_START = datetime(2025, 4, 24)
DAY_MISSION_END = datetime(2025, 4, 25)
DAY_MISSION_OPTIONS = datetime(2025, 4, 29)


def log_drive_activity(mission, user, day, hour_start=14, hour_end=15):
    log_activity(
        submitter=user,
        user=user,
        mission=mission,
        type=ActivityType.DRIVE,
        switch_mode=False,
        reception_time=datetime.combine(day, time(hour=hour_end, minute=0)),
        start_time=datetime.combine(day, time(hour=hour_start, minute=0)),
        end_time=datetime.combine(day, time(hour=hour_end, minute=0)),
    )


def end_mission_and_validate(db, mission, user, day, hour_end=15):
    db.session.add(
        MissionEnd(
            submitter=user,
            reception_time=datetime.combine(
                day, time(hour=hour_end, minute=0)
            ),
            user=user,
            mission=mission,
        )
    )
    validate_mission(
        submitter=user,
        mission=mission,
        for_user=user,
    )


def run_scenario_export_excel():

    ## Two companies
    company_1 = CompanyFactory.create(
        usual_name="Company Without Settings",
        siren="0000091",
        allow_transfers=False,
        require_kilometer_data=False,
    )
    company_2 = CompanyFactory.create(
        usual_name="Company With Settings",
        siren="0000092",
        allow_transfers=True,
        require_kilometer_data=True,
    )

    ## An admin for both companies
    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Busy",
        last_name="Admin",
    )
    for c in [company_1, company_2]:
        EmploymentFactory.create(
            company=c, submitter=admin, user=admin, has_admin_rights=True
        )

    ## Vehicles
    for idx, c in enumerate([company_1, company_2]):
        db.session.add(
            Vehicle(
                registration_number=f"XXX-001-CORP{idx + 1}",
                alias=f"Vehicule 1 - Corp {idx + 1}",
                company_id=c.id,
            )
        )

        ## Adresses
        db.session.add(
            CompanyKnownAddress(
                alias=f"Entrepot {idx + 1 }",
                address=Address.get_or_create(
                    geo_api_data=None, manual_address="1, rue de Paris"
                ),
                company_id=c.id,
            )
        )

    employee_1 = UserFactory.create(
        email=EMPLOYEE_1_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Michael",
        last_name="Jordan",
    )
    employee_2 = UserFactory.create(
        email=EMPLOYEE_2_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Larry",
        last_name="Bird",
    )
    employee_3 = UserFactory.create(
        email=EMPLOYEE_3_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Michael",
        last_name="Jordan",
    )
    employee_4 = UserFactory.create(
        email=EMPLOYEE_4_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Larry",
        last_name="Bird",
    )

    employees = {
        company_1.id: [employee_1, employee_2],
        company_2.id: [employee_3, employee_4],
    }
    for c in [company_1, company_2]:
        for e in employees[c.id]:
            EmploymentFactory.create(
                company=c,
                submitter=admin,
                user=e,
                has_admin_rights=False,
            )

            ## work on a french bank holiday
            holiday_mission = Mission(
                name="Mission Jour Férié",
                company=c,
                reception_time=datetime.combine(
                    A_FRENCH_HOLIDAY, time(hour=10, minute=0)
                ),
                submitter=e,
            )
            db.session.add(holiday_mission)
            db.session.commit()

            ## Work on a sunday
            sunday_mission = Mission(
                name="Mission Dimanche",
                company=c,
                reception_time=datetime.combine(
                    A_SUNDAY, time(hour=10, minute=0)
                ),
                submitter=e,
            )

            ## Three missions on same day
            mission_same_day_1 = Mission(
                name="Mission 1/3",
                company=c,
                reception_time=datetime.combine(
                    DAY_MULTIPLE_MISSIONS, time(hour=8, minute=0)
                ),
                submitter=e,
            )
            mission_same_day_2 = Mission(
                name="Mission 2/3",
                company=c,
                reception_time=datetime.combine(
                    DAY_MULTIPLE_MISSIONS, time(hour=11, minute=0)
                ),
                submitter=e,
            )
            mission_same_day_3 = Mission(
                name="Mission 3/3",
                company=c,
                reception_time=datetime.combine(
                    DAY_MULTIPLE_MISSIONS, time(hour=17, minute=0)
                ),
                submitter=e,
            )

            # A mission starts on one day and finishes on another
            mission_on_two_days = Mission(
                name="Mission sur 2 jours",
                company=c,
                reception_time=datetime.combine(
                    DAY_MISSION_START, time(hour=19, minute=0)
                ),
                submitter=e,
            )

            mission_with_lot_of_options = Mission(
                name="Mission Options",
                company=c,
                reception_time=datetime.combine(
                    DAY_MISSION_OPTIONS, time(hour=10, minute=0)
                ),
                submitter=e,
                vehicle_id=c.vehicles[0].id,
            )
            db.session.add(holiday_mission)
            db.session.commit()

            # Start adress
            start_address = Address.get_or_create(
                geo_api_data=None, manual_address="123 rue du Port"
            )
            db.session.add(start_address)
            location_entry = LocationEntry(
                _address=start_address,
                mission=mission_with_lot_of_options,
                reception_time=datetime.combine(
                    DAY_MISSION_OPTIONS, time(hour=10, minute=0)
                ),
                submitter=e,
                type=LocationEntryType.MISSION_START_LOCATION,
            )
            location_entry.register_kilometer_reading(
                512,
                datetime.combine(DAY_MISSION_OPTIONS, time(hour=10, minute=0)),
            )

            with AuthenticatedUserContext(user=e):
                log_drive_activity(holiday_mission, e, A_FRENCH_HOLIDAY)
                end_mission_and_validate(
                    db, holiday_mission, e, A_FRENCH_HOLIDAY
                )

                log_drive_activity(sunday_mission, e, A_SUNDAY)
                end_mission_and_validate(db, sunday_mission, e, A_SUNDAY)

                log_drive_activity(
                    mission_same_day_1,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_start=8,
                    hour_end=10,
                )
                end_mission_and_validate(
                    db,
                    mission_same_day_1,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_end=10,
                )
                log_drive_activity(
                    mission_same_day_2,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_start=11,
                    hour_end=13,
                )
                end_mission_and_validate(
                    db,
                    mission_same_day_2,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_end=13,
                )
                log_drive_activity(
                    mission_same_day_3,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_start=17,
                    hour_end=19,
                )
                end_mission_and_validate(
                    db,
                    mission_same_day_3,
                    e,
                    DAY_MULTIPLE_MISSIONS,
                    hour_end=19,
                )

                log_activity(
                    submitter=e,
                    user=e,
                    mission=mission_on_two_days,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=datetime.combine(
                        DAY_MISSION_END, time(hour=10, minute=0)
                    ),
                    start_time=datetime.combine(
                        DAY_MISSION_START, time(hour=19, minute=0)
                    ),
                    end_time=datetime.combine(
                        DAY_MISSION_END, time(hour=10, minute=0)
                    ),
                )
                end_mission_and_validate(
                    db, mission_on_two_days, e, DAY_MISSION_END, hour_end=10
                )

                log_drive_activity(
                    mission_with_lot_of_options, e, DAY_MISSION_OPTIONS
                )
                end_mission_and_validate(
                    db, mission_with_lot_of_options, e, DAY_MISSION_OPTIONS
                )

                location_entry = LocationEntry(
                    _address=start_address,
                    mission=mission_with_lot_of_options,
                    reception_time=datetime.combine(
                        DAY_MISSION_OPTIONS, time(hour=19, minute=0)
                    ),
                    submitter=e,
                    type=LocationEntryType.MISSION_END_LOCATION,
                )
                location_entry.register_kilometer_reading(
                    781,
                    datetime.combine(
                        DAY_MISSION_OPTIONS, time(hour=19, minute=0)
                    ),
                )

                with AuthenticatedUserContext(user=admin):
                    log_activity(
                        submitter=admin,
                        user=e,
                        mission=mission_with_lot_of_options,
                        type=ActivityType.TRANSFER,
                        switch_mode=False,
                        reception_time=datetime.combine(
                            DAY_MISSION_OPTIONS, time(hour=19, minute=0)
                        ),
                        start_time=datetime.combine(
                            DAY_MISSION_OPTIONS, time(hour=8, minute=0)
                        ),
                        end_time=datetime.combine(
                            DAY_MISSION_OPTIONS, time(hour=10, minute=0)
                        ),
                    )
                    for m in [
                        holiday_mission,
                        sunday_mission,
                        mission_same_day_1,
                        mission_same_day_2,
                        mission_same_day_3,
                        mission_on_two_days,
                        mission_with_lot_of_options,
                    ]:
                        validate_mission(
                            submitter=admin,
                            mission=m,
                            for_user=e,
                        )
                db.session.commit()

    db.session.commit()
