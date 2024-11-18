from datetime import datetime

from dateutil.tz import gettz

from app import db
from app.domain.log_activities import log_activity
from app.domain.regulations_per_day import NATINF_32083, NATINF_11292
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import HOUR
from app.helpers.submitter_type import SubmitterType
from app.models import (
    Mission,
    RegulatoryAlert,
    User,
    RegulationCheck,
)
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed import UserFactory, EmploymentFactory, AuthenticatedUserContext
from app.seed.helpers import get_time, get_date
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestMaximumWorkDayTime(RegulationsTest):
    @staticmethod
    def _get_alert(days_ago, submitter_type=SubmitterType.ADMIN):
        day_start = get_date(days_ago)
        return RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == submitter_type,
        ).one_or_none()

    def test_max_work_day_time_by_employee_success(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="Transfer & night work tarification but not legislation",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=3),
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    ActivityType.TRANSFER,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                ],
            ],
        )
        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.EMPLOYEE
        )
        self.assertIsNone(regulatory_alert)

    def test_max_work_day_time_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="3h work (night) + 8h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                ],
            ],
        )
        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.EMPLOYEE
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 11 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=16),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_32083)

    def test_max_work_day_time_by_employee_no_night_work_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="5h work + 8h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=21),
                ],
            ],
        )
        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.EMPLOYEE
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 13 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=7),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=21),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_11292)

    def test_max_work_day_time_depending_on_business(self):
        how_many_days_ago = 5

        ## By default, employee is TRM
        self._log_and_validate_mission(
            mission_name="11h - ok",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
            ],
        )

        # 11h  is fine, no alert
        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.EMPLOYEE
        )
        self.assertIsNone(regulatory_alert)

        self.convert_employee_to_trv()

        how_many_days_ago = 2

        ## now employee is TRV
        self._log_and_validate_mission(
            mission_name="11h - ko",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
            ],
        )

        # 11h  is above limit, alert
        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.EMPLOYEE
        )
        self.assertIsNotNone(regulatory_alert)

    def test_max_work_day_time_by_admin_failure(self):
        how_many_days_ago = 2

        mission = self._log_and_validate_mission(
            mission_name="3h work (night) + 10h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=17),
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin, mission=mission, for_user=self.employee
            )

        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 13 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=17),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_32083)

    def test_max_work_day_time_in_guyana_success(self):
        company = self.company
        admin = self.admin
        how_many_days_ago = 2

        GY_TZ_NAME = "America/Cayenne"
        GY_TIMEZONE = gettz(GY_TZ_NAME)

        employee = UserFactory.create(
            email="employee-guyana@email.com",
            password="password",
            timezone_name=GY_TZ_NAME,
        )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )

        mission = Mission(
            name="11h drive in Guyana with night work",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission)

        with AuthenticatedUserContext(user=employee):
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(
                    how_many_days_ago, hour=17, tz=GY_TIMEZONE
                ),
                start_time=get_time(how_many_days_ago, hour=6, tz=GY_TIMEZONE),
                end_time=get_time(how_many_days_ago, hour=17, tz=GY_TIMEZONE),
            )

            # Guyana UTC-4 = France UTC+2
            # Guyana: 6h -> 17h (day)
            # France: 12h -> 23h (night)

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_no_night_work_hours_start(self):
        how_many_days_ago = 2
        mission_no_night_hours = self._log_and_validate_mission(
            mission_name="Pas de travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=11),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=50
                    ),
                    ActivityType.WORK,
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin,
                mission=mission_no_night_hours,
                for_user=self.employee,
            )

        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)

    def test_no_night_work_hours_end(self):
        how_many_days_ago = 2
        mission_no_night_hours = self._log_and_validate_mission(
            mission_name="Pas de travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=5, minute=5
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=17, minute=35
                    ),
                    ActivityType.WORK,
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin,
                mission=mission_no_night_hours,
                for_user=self.employee,
            )

        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)

    def test_night_work_hours_start(self):
        how_many_days_ago = 2
        mission_night_hours = self._log_and_validate_mission(
            mission_name="Travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=0,
                        minute=30,
                    ),
                    ActivityType.WORK,
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin,
                mission=mission_night_hours,
                for_user=self.employee,
            )

        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)

    def test_night_work_hours_end(self):
        how_many_days_ago = 2
        mission_night_hours = self._log_and_validate_mission(
            mission_name="Travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=4, minute=50
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=17, minute=10
                    ),
                    ActivityType.WORK,
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin,
                mission=mission_night_hours,
                for_user=self.employee,
            )

        regulatory_alert = TestMaximumWorkDayTime._get_alert(
            days_ago=how_many_days_ago
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)
