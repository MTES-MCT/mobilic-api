import datetime

from app import db
from app.domain.expenditure import log_expenditure
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import (
    MissionEnd,
    Vehicle,
    CompanyKnownAddress,
    Address,
)
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import (
    get_time,
    get_date,
    create_mission,
    DEFAULT_PASSWORD,
)

NB_COMPANIES = 2
NB_EMPLOYEES = 2
NB_HISTORY = 7
INTERVAL_HISTORY = 1
ADMIN_EMAIL = "busy.admin@test.com"


def _add_employee(email, first_name, last_name, company, admin):
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


def run_scenario_busy_admin():
    companies = [
        CompanyFactory.create(
            usual_name=f"Busy Corp {i + 1}", siren=f"000000{i}"
        )
        for i in range(NB_COMPANIES)
    ]

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Busy",
        last_name="Admin",
    )

    for idx_company, company in enumerate(companies):

        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )

        ## Vehicles
        vehicles = []
        for idx_vehicle in range(1, 3):
            vehicle = Vehicle(
                registration_number=f"XXX-00{idx_vehicle}-CORP{idx_company + 1}",
                alias=f"Vehicule {idx_vehicle} - Corp {idx_company + 1}",
                submitter=admin,
                company_id=company.id,
            )
            db.session.add(vehicle)
            vehicles.append(vehicle)

        ## Addresses
        addresses = []
        address = CompanyKnownAddress(
            alias=f"Entrepot Corp {idx_company + 1}",
            address=Address.get_or_create(
                geo_api_data=None, manual_address="1, rue de Paris"
            ),
            company_id=company.id,
        )
        db.session.add(address)
        addresses.append(address)

        for i in range(NB_EMPLOYEES):
            employee = UserFactory.create(
                email=f"busy.employee{i + 1}@busycorp{idx_company + 1}.com",
                password=DEFAULT_PASSWORD,
                first_name=f"Bérénice {i + 1}",
                last_name=f"Corp {idx_company + 1}",
            )
            EmploymentFactory.create(
                company=company,
                submitter=admin,
                user=employee,
                has_admin_rights=False,
            )

            # TODAY: a mission still pending
            today_mission = create_mission(
                name=f"Mission Pending {idx_company + 1}:{i + 1}",
                company=company,
                time=datetime.datetime.now(),
                submitter=employee,
                vehicle=vehicles[0],
                address=addresses[0],
                add_location_entry=True,
            )

            # YESTERDAY: a mission to validate
            yesterday_mission = create_mission(
                name=f"Mission To Validate {idx_company + 1}:{i + 1}",
                company=company,
                time=get_time(how_many_days_ago=2, hour=8),
                submitter=employee,
                vehicle=vehicles[0],
                address=addresses[0],
                add_location_entry=True,
            )

            # CREATES HISTORY MISSIONS
            history_missions = {}
            for idx_history in range(NB_HISTORY):
                how_many_days_ago = 3 + idx_history * INTERVAL_HISTORY
                tmp_mission = create_mission(
                    name=f"Mission Past {how_many_days_ago} {idx_company + 1}:{i + 1}",
                    company=company,
                    time=get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    submitter=employee,
                    vehicle=vehicles[0],
                    address=addresses[0],
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
                how_many_days_ago = 3 + idx_history * INTERVAL_HISTORY
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

    db.session.commit()

    from app.tests.helpers import make_authenticated_request, ApiRequests

    ## An employee who takes holidays
    holiday_employee = _add_employee(
        email="holiday@busycorp.com",
        first_name="Holly",
        last_name="Day",
        company=companies[0],
        admin=admin,
    )
    make_authenticated_request(
        time=get_time(how_many_days_ago=5, hour=18),
        submitter_id=holiday_employee.id,
        query=ApiRequests.log_holiday,
        variables=dict(
            companyId=companies[0].id,
            userId=holiday_employee.id,
            startTime=get_time(how_many_days_ago=5, hour=10),
            endTime=get_time(how_many_days_ago=5, hour=16),
            title="Accident du travail",
        ),
    )
    make_authenticated_request(
        time=get_time(how_many_days_ago=5, hour=18),
        submitter_id=holiday_employee.id,
        query=ApiRequests.log_holiday,
        variables=dict(
            companyId=companies[0].id,
            userId=holiday_employee.id,
            startTime=get_time(how_many_days_ago=12, hour=10),
            endTime=get_time(how_many_days_ago=8, hour=16),
            title="Congé payé",
        ),
    )
    make_authenticated_request(
        time=get_time(how_many_days_ago=5, hour=18),
        submitter_id=holiday_employee.id,
        query=ApiRequests.log_holiday,
        variables=dict(
            companyId=companies[0].id,
            userId=holiday_employee.id,
            startTime=get_time(how_many_days_ago=14, hour=8),
            endTime=get_time(how_many_days_ago=14, hour=11),
            title="Formation",
        ),
    )
    afternoon_mission = create_mission(
        name="Mission Apres Midi",
        company=companies[0],
        time=get_time(how_many_days_ago=5, hour=18),
        submitter=holiday_employee,
    )
    db.session.commit()

    with AuthenticatedUserContext(user=holiday_employee):
        log_activity(
            submitter=holiday_employee,
            user=holiday_employee,
            mission=afternoon_mission,
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=14, hour=19),
            start_time=get_time(how_many_days_ago=14, hour=14),
            end_time=get_time(how_many_days_ago=14, hour=18),
        )
        db.session.commit()
        validate_mission(
            submitter=holiday_employee,
            mission=afternoon_mission,
            for_user=holiday_employee,
        )
