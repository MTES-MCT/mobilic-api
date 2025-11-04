import datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import MissionEnd
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import (
    add_employee,
    get_time,
    create_mission,
    DEFAULT_PASSWORD,
)
from app.seed.scenarios import load_missions

NB_COMPANIES = 2
NB_EMPLOYEES = 2
NB_HISTORY = 7
INTERVAL_HISTORY = 1
ADMIN_EMAIL = "busy.admin@test.com"


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

    for company in companies:
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )
    db.session.commit()

    for company in companies:
        load_missions.run(
            company, admin, NB_EMPLOYEES, NB_HISTORY, INTERVAL_HISTORY
        )

    db.session.commit()

    from app.tests.helpers import make_authenticated_request, ApiRequests

    ## An employee who takes holidays
    holiday_employee = add_employee(
        company=companies[0],
        admin=admin,
        email="holiday@busycorp.com",
        first_name="Holly",
        last_name="Day",
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

    ## An employee with deleted activities and missions
    deleted_mission_employee = add_employee(
        company=companies[0],
        admin=admin,
        email="deleted.mission@busycorp.com",
        first_name="Agathe",
        last_name="Ortega",
    )
    finished_mission = create_mission(
        name="Finished Mission",
        company=companies[0],
        time=datetime.datetime.now(),
        submitter=deleted_mission_employee,
    )
    running_mission = create_mission(
        name="Running Mission",
        company=companies[0],
        time=datetime.datetime.now(),
        submitter=deleted_mission_employee,
    )
    db.session.commit()
    with AuthenticatedUserContext(user=deleted_mission_employee):
        log_activity(
            submitter=deleted_mission_employee,
            user=deleted_mission_employee,
            mission=finished_mission,
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=15, hour=15),
            start_time=get_time(how_many_days_ago=15, hour=14),
            end_time=get_time(how_many_days_ago=15, hour=15),
        )
        db.session.add(
            MissionEnd(
                submitter=deleted_mission_employee,
                reception_time=get_time(how_many_days_ago=15, hour=15),
                user=deleted_mission_employee,
                mission=finished_mission,
            )
        )
        validate_mission(
            submitter=deleted_mission_employee,
            mission=finished_mission,
            for_user=deleted_mission_employee,
        )
        log_activity(
            submitter=deleted_mission_employee,
            user=deleted_mission_employee,
            mission=running_mission,
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=12, hour=15),
            start_time=get_time(how_many_days_ago=12, hour=14),
        )
    db.session.commit()

    from app.tests.helpers import make_authenticated_request, ApiRequests

    # Admin cancels missions
    for mission_id in [finished_mission.id, running_mission.id]:
        make_authenticated_request(
            time=get_time(how_many_days_ago=9, hour=17),
            submitter_id=admin.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=mission_id,
                user_id=deleted_mission_employee.id,
            ),
        )

    mission_with_deleted_activities = create_mission(
        name="Mission With Deleted Activities",
        company=companies[0],
        time=datetime.datetime.now(),
        submitter=deleted_mission_employee,
    )
    db.session.commit()

    with AuthenticatedUserContext(user=deleted_mission_employee):
        for hour_ in [10, 13, 16]:
            log_activity(
                submitter=deleted_mission_employee,
                user=deleted_mission_employee,
                mission=mission_with_deleted_activities,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago=14, hour=hour_ + 1),
                start_time=get_time(how_many_days_ago=14, hour=hour_),
                end_time=get_time(how_many_days_ago=14, hour=hour_ + 1),
            )
        db.session.commit()

    make_authenticated_request(
        time=get_time(how_many_days_ago=14, hour=20),
        submitter_id=deleted_mission_employee.id,
        query=ApiRequests.cancel_activity,
        variables=dict(
            activityId=mission_with_deleted_activities.activities_for(
                deleted_mission_employee
            )[0].id,
        ),
    )
    make_authenticated_request(
        time=get_time(how_many_days_ago=14, hour=21),
        submitter_id=deleted_mission_employee.id,
        query=ApiRequests.validate_mission,
        variables=dict(
            missionId=mission_with_deleted_activities.id,
            usersIds=[deleted_mission_employee.id],
        ),
    )

    make_authenticated_request(
        time=get_time(how_many_days_ago=14, hour=23),
        submitter_id=admin.id,
        query=ApiRequests.validate_mission,
        variables=dict(
            missionId=mission_with_deleted_activities.id,
            usersIds=[deleted_mission_employee.id],
            activityItems=[
                {
                    "cancel": {
                        "activityId": mission_with_deleted_activities.activities_for(
                            deleted_mission_employee
                        )[
                            1
                        ].id
                    }
                }
            ],
        ),
    )
