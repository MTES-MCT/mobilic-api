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
from app.models.business import BusinessType
from app.models.regulation_check import RegulationCheckType
from app.seed import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import get_time, get_date
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


def _get_alert(days_ago, submitter_type=SubmitterType.EMPLOYEE):
    day_start = get_date(days_ago)

    return RegulatoryAlert.query.filter(
        RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
        RegulatoryAlert.regulation_check.has(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ),
        RegulatoryAlert.day == day_start,
        RegulatoryAlert.submitter_type == submitter_type,
    ).one_or_none()


class TestMaximumWorkDayTime(RegulationsTest):
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
                    get_time(
                        how_many_days_ago=how_many_days_ago,
                        hour=13,
                        minute=30,
                    ),
                    ActivityType.DRIVE,
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=13, minute=30
                    ),
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                    ActivityType.DRIVE,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_max_work_day_time_by_employee_failure(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="TRV work time > 10 hours",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(
                        how_many_days_ago=how_many_days_ago,
                        hour=16,
                    ),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    def test_max_work_day_time_by_admin_failure(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="TRV work time > 10 hours",
            submitter=self.admin,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(
                        how_many_days_ago=how_many_days_ago,
                        hour=16,
                    ),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.ADMIN
        )
        self.assertIsNotNone(regulatory_alert)

    def test_max_work_day_time_by_employee_no_night_work_failure(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="No night work but 13 hours of work",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(
                        how_many_days_ago=how_many_days_ago,
                        hour=18,
                    ),
                    ActivityType.DRIVE,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(
            regulatory_alert,
        )
        extra_info = regulatory_alert.extra
        self.assertFalse(extra_info["night_work"])
        self.assertEqual(extra_info["sanction_code"], NATINF_11292)
        self.assertEqual(extra_info["sanction_code"], NATINF_11292)

    def test_max_work_day_time_depending_on_business(self):
        how_many_days_ago = 5

        # Same employee in different companies. One is TRV FREQUENT (max 10h when amplitude > 13h and max 9h if amplitude > 13h) one is TRM LONG_DISTANCE (max 12h)
        trv_frequent_company = CompanyFactory.create(
            name="trv company"
        )  # TRV - by default no specific business
        trm_long_distance_company = CompanyFactory.create(
            name="trm company", business_type=BusinessType.LONG_DISTANCE
        )

        # TRV - FREQUENT
        EmploymentFactory.create(
            company=trv_frequent_company, submitter=self.employee
        )

        # TRM - LONG DISTANCE
        EmploymentFactory.create(
            company=trm_long_distance_company, submitter=self.employee
        )

        # Workday with 11 hours of work.
        # TRV (FREQUENT by default) : alert expected (> 10h)
        # TRM (LONG_DISTANCE) : no alert (< 12h)
        with AuthenticatedUserContext(user=self.employee):
            # TRV FREQUENT : alert expected for 11h work
            self._log_and_validate_mission(
                mission_name="11 hours worked mission for TRV frequent with high amplitude (15h)",
                submitter=self.employee,
                company=trv_frequent_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=7),
                        get_time(how_many_days_ago=how_many_days_ago, hour=18),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=15,
            )

            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.user == self.employee,
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.type
                    == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ),
                RegulatoryAlert.company == trv_frequent_company,
            ).one_or_none()
            # Alert expected (11h > 9h because amplitude > 13h for TRV FREQUENT)
            self.assertIsNotNone(regulatory_alert)

            # TRM LONG_DISTANCE : no alert for 11h work
            self._log_and_validate_mission(
                mission_name="11 hours worked mission TRM long distance",
                submitter=self.employee,
                company=trm_long_distance_company,
                work_periods=[
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=7
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=18
                        ),
                        ActivityType.DRIVE,
                    ]
                ],
            )

            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.user == self.employee,
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.type
                    == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ),
                RegulatoryAlert.company == trm_long_distance_company,
            ).one_or_none()
            # No alert (11h < 12h for TRM)
            self.assertIsNone(regulatory_alert)

    def test_ok_trv_frequent_low_amplitude(self):
        how_many_days_ago = 5
        # TRV FREQUENT company with low amplitude (8h), 9h of work should not trigger alert
        trv_frequent_company = CompanyFactory.create(
            name="trv_frequent", business_type=BusinessType.FREQUENT
        )
        EmploymentFactory.create(
            company=trv_frequent_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV frequent with low amplitude (8h) and 9h work",
                submitter=self.employee,
                company=trv_frequent_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=8,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_frequent_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNone(regulatory_alert)

    def test_ok_trv_frequent_high_amplitude(self):
        how_many_days_ago = 5
        # TRV FREQUENT company with high amplitude (15h), 9h of work should not trigger alert
        trv_frequent_company = CompanyFactory.create(
            name="trv_frequent", business_type=BusinessType.FREQUENT
        )
        EmploymentFactory.create(
            company=trv_frequent_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV frequent with high amplitude (15h) and 9h work",
                submitter=self.employee,
                company=trv_frequent_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=15,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_frequent_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNone(regulatory_alert)

    def test_ko_trv_frequent_low_amplitude(self):
        how_many_days_ago = 5
        # TRV FREQUENT company with low amplitude (8h), 11h of work should trigger alert
        trv_frequent_company = CompanyFactory.create(
            name="trv_frequent", business_type=BusinessType.FREQUENT
        )
        EmploymentFactory.create(
            company=trv_frequent_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV frequent with low amplitude (8h) and 11h work",
                submitter=self.employee,
                company=trv_frequent_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=6),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=8,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_frequent_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNotNone(regulatory_alert)

    def test_ko_trv_frequent_high_amplitude(self):
        how_many_days_ago = 5
        # TRV FREQUENT company with high amplitude (15h), 10h of work should trigger alert (limit = 9h)
        trv_frequent_company = CompanyFactory.create(
            name="trv_frequent", business_type=BusinessType.FREQUENT
        )
        EmploymentFactory.create(
            company=trv_frequent_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV frequent with high amplitude (15h) and 10h work",
                submitter=self.employee,
                company=trv_frequent_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=18),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=15,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_frequent_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNotNone(regulatory_alert)

    def test_ok_t3p_low_amplitude(self):
        how_many_days_ago = 5
        # TRV T3P (DEFAULT) company with low amplitude (10h), 9h of work should not trigger alert
        trv_t3p_company = CompanyFactory.create(name="trv_t3p")
        EmploymentFactory.create(
            company=trv_t3p_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV T3P with low amplitude (10h) and 9h work",
                submitter=self.employee,
                company=trv_t3p_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=10,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_t3p_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNone(regulatory_alert)

    def test_ok_t3p_high_amplitude(self):
        how_many_days_ago = 5
        # TRV T3P (DEFAULT) company with high amplitude (15h), 9h of work should not trigger alert
        trv_t3p_company = CompanyFactory.create(name="trv_t3p")
        EmploymentFactory.create(
            company=trv_t3p_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV T3P with high amplitude (15h) and 9h work",
                submitter=self.employee,
                company=trv_t3p_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=15,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_t3p_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNone(regulatory_alert)

    def test_ko_t3p_low_amplitude(self):
        how_many_days_ago = 5
        # TRV T3P (DEFAULT) company with low amplitude (10h), 11h of work should trigger alert
        trv_t3p_company = CompanyFactory.create(name="trv_t3p")
        EmploymentFactory.create(
            company=trv_t3p_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV T3P with low amplitude (10h) and 11h work",
                submitter=self.employee,
                company=trv_t3p_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=6),
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=10,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_t3p_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNotNone(regulatory_alert)

    def test_ko_t3p_high_amplitude(self):
        how_many_days_ago = 5
        # TRV T3P (DEFAULT) company with high amplitude (15h), 10h of work should trigger alert (limit = 9h)
        trv_t3p_company = CompanyFactory.create(name="trv_t3p")
        EmploymentFactory.create(
            company=trv_t3p_company, submitter=self.employee
        )

        with AuthenticatedUserContext(user=self.employee):
            self._log_and_validate_mission(
                mission_name="TRV T3P with high amplitude (15h) and 10h work",
                submitter=self.employee,
                company=trv_t3p_company,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=8),
                        get_time(how_many_days_ago=how_many_days_ago, hour=18),
                        ActivityType.DRIVE,
                    ]
                ],
                service_duration_hours=15,
            )
            regulatory_alert = RegulatoryAlert.query.filter(
                RegulatoryAlert.company == trv_t3p_company,
                RegulatoryAlert.user == self.employee,
            ).one_or_none()
            self.assertIsNotNone(regulatory_alert)

    def test_night_hours_start(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Night work start",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=7),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_no_night_hours_start(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="No night work start",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_night_hours_end(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Night work end",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=1),
                    get_time(how_many_days_ago=how_many_days_ago, hour=9),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_no_night_hours_end(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="No night work end",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=5, minute=1
                    ),
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_max_work_day_time_in_guyana_success(self):
        how_many_days_ago = 2

        # Create work day in Guyana timezone (UTC-3)
        guyana_tz = gettz("America/Cayenne")

        self._log_and_validate_mission(
            mission_name="Work in Guyana timezone",
            submitter=self.employee,
            work_periods=[
                [
                    datetime(
                        get_time(how_many_days_ago=how_many_days_ago).year,
                        get_time(how_many_days_ago=how_many_days_ago).month,
                        get_time(how_many_days_ago=how_many_days_ago).day,
                        8,
                        0,
                        tzinfo=guyana_tz,
                    ),
                    datetime(
                        get_time(how_many_days_ago=how_many_days_ago).year,
                        get_time(how_many_days_ago=how_many_days_ago).month,
                        get_time(how_many_days_ago=how_many_days_ago).day,
                        17,
                        0,
                        tzinfo=guyana_tz,
                    ),
                    ActivityType.DRIVE,
                ]
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_night_work_on_two_days(self):
        how_many_days_ago = 2

        # Create a mission that spans two days with night work
        self._log_and_validate_mission(
            mission_name="Night work spanning two days",
            submitter=self.employee,
            work_periods=[
                # Day 1: 23:00 - 01:00 (2h with night work due to midnight crossing)
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=1),
                    ActivityType.DRIVE,
                ],
                # Day 2: 06:00 - 15:00 (9h normal work)
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=15),
                    ActivityType.DRIVE,
                ],
            ],
        )

        # The night work detection should apply, limiting work to 10h instead of 12h
        # Total work: 2h + 9h = 11h > 10h (night work limit) -> should trigger alert
        alert = _get_alert(days_ago=2)
        self.assertIsNotNone(alert)
