import datetime
from app.models.address import Address
from app.models.company_known_address import CompanyKnownAddress
from app.models.vehicle import Vehicle
from app.seed.helpers import add_employee, create_mission, get_date, get_time


from app import db
from app.domain.expenditure import log_expenditure
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import MissionEnd
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.seed import AuthenticatedUserContext


def run(company, admin, nb_employees, nb_history, interval_history):
    from faker import Faker

    fake = Faker("fr_FR")

    vehicle = Vehicle(
        registration_number=fake.license_plate(),
        alias=fake.word(),
        submitter=admin,
        company_id=company.id,
    )
    db.session.add(vehicle)

    address = CompanyKnownAddress(
        alias=fake.company(),
        address=Address.get_or_create(
            geo_api_data=None, manual_address=fake.address()
        ),
        company_id=company.id,
    )
    db.session.add(address)

    for i in range(nb_employees):
        employee = add_employee(
            email=f"busy.{fake.email()}",
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            company=company,
            admin=admin,
        )

        # TODAY: a mission still pending
        today_mission = create_mission(
            name=f"Pending {fake.word()}",
            company=company,
            time=datetime.datetime.now(),
            submitter=employee,
            vehicle=vehicle,
            address=address,
            add_location_entry=True,
        )

        # YESTERDAY: a mission to validate
        yesterday_mission = create_mission(
            name=f"To Validate {fake.word()}",
            company=company,
            time=get_time(how_many_days_ago=2, hour=8),
            submitter=employee,
            vehicle=vehicle,
            address=address,
            add_location_entry=True,
        )

        # CREATES HISTORY MISSIONS
        history_missions = {}
        for idx_history in range(nb_history):
            how_many_days_ago = 3 + idx_history * interval_history
            tmp_mission = create_mission(
                name=f"Past {how_many_days_ago} {fake.word()}",
                company=company,
                time=get_time(how_many_days_ago=how_many_days_ago, hour=8),
                submitter=employee,
                vehicle=vehicle,
                address=address,
                add_location_entry=True,
            )
            history_missions[idx_history] = tmp_mission
        db.session.commit()

        with AuthenticatedUserContext(user=employee):
            log_activity(
                submitter=employee,
                user=employee,
                mission=today_mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago=1, hour=15),
                start_time=get_time(how_many_days_ago=1, hour=14),
                end_time=get_time(how_many_days_ago=1, hour=15),
            )
            log_activity(
                submitter=employee,
                user=employee,
                mission=yesterday_mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago=2, hour=15),
                start_time=get_time(how_many_days_ago=2, hour=14),
                end_time=get_time(how_many_days_ago=2, hour=15),
            )
            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago=2, hour=15),
                    user=employee,
                    mission=yesterday_mission,
                )
            )
            log_expenditure(
                submitter=employee,
                user=employee,
                mission=yesterday_mission,
                type=ExpenditureType.DAY_MEAL,
                reception_time=get_time(how_many_days_ago=2, hour=15),
                spending_date=get_date(how_many_days_ago=2),
            )
            validate_mission(
                submitter=employee,
                mission=yesterday_mission,
                for_user=employee,
            )

        for idx_history, history_mission in history_missions.items():
            how_many_days_ago = 3 + idx_history * interval_history
            with AuthenticatedUserContext(user=employee):
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=history_mission,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_time(
                        how_many_days_ago=(how_many_days_ago),
                        hour=15,
                    ),
                    start_time=get_time(
                        how_many_days_ago=(how_many_days_ago),
                        hour=14,
                    ),
                    end_time=get_time(
                        how_many_days_ago=(how_many_days_ago),
                        hour=15,
                    ),
                )
                db.session.add(
                    MissionEnd(
                        submitter=employee,
                        reception_time=get_time(
                            how_many_days_ago=(how_many_days_ago),
                            hour=15,
                        ),
                        user=employee,
                        mission=history_mission,
                    )
                )
                for expenditure_type in ExpenditureType:
                    log_expenditure(
                        submitter=employee,
                        user=employee,
                        mission=history_mission,
                        type=expenditure_type,
                        reception_time=get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=15,
                        ),
                        spending_date=get_date(
                            how_many_days_ago=how_many_days_ago
                        ),
                    )
                validate_mission(
                    submitter=employee,
                    mission=history_mission,
                    for_user=employee,
                )
            with AuthenticatedUserContext(user=admin):
                validate_mission(
                    submitter=admin,
                    mission=history_mission,
                    for_user=employee,
                )
            db.session.commit()
