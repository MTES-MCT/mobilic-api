from datetime import datetime, date

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    compute_be_compliant,
    is_alert_above_tolerance_limit,
    COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES,
    COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES,
    COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES,
    COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES,
)
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import previous_month_period
from app.models import Mission, RegulatoryAlert, RegulationCheck
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed import (
    CompanyFactory,
    UserFactory,
    AuthenticatedUserContext,
)
from app.tests import BaseTest
from app.tests.helpers import init_regulation_checks_data


class TestCertificateBeCompliant(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        self.start, self.end = previous_month_period(date(2023, 3, 28))

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_regulatory_alert_minimum_daily_rest_above_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ).first(),
            extra={
                "min_daily_break_in_hours": 10,
                "breach_period_max_break_in_seconds": 10 * 60 * 60
                - (COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES + 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertTrue(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_minimum_daily_rest_within_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ).first(),
            extra={
                "min_daily_break_in_hours": 10,
                "breach_period_max_break_in_seconds": 10 * 60 * 60
                - (COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES - 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertFalse(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_maximum_work_day_time_above_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ).first(),
            extra={
                "max_work_range_in_hours": 10,
                "work_range_in_seconds": 10 * 60 * 60
                + (COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES + 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertTrue(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_maximum_work_day_time_within_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ).first(),
            extra={
                "max_work_range_in_hours": 10,
                "work_range_in_seconds": 10 * 60 * 60
                + (COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES - 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertFalse(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_minimum_work_day_break_above_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ).first(),
            extra={
                "min_break_time_in_minutes": 45,
                "total_break_time_in_seconds": 45 * 60
                - (COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES + 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertTrue(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_minimum_work_day_break_within_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ).first(),
            extra={
                "min_break_time_in_minutes": 45,
                "total_break_time_in_seconds": 45 * 60
                - (COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES - 2) * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertFalse(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_maximum_uninterrumpted_time_above_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ).first(),
            extra={
                "max_uninterrupted_work_in_hours": 8,
                "longest_uninterrupted_work_in_seconds": 8 * 60 * 60
                + (
                    COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES
                    + 2
                )
                * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertTrue(is_alert_above_tolerance_limit(regulatory_alert))

    def test_regulatory_alert_maximum_uninterrumpted_time_within_limit(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ).first(),
            extra={
                "max_uninterrupted_work_in_hours": 8,
                "longest_uninterrupted_work_in_seconds": 8 * 60 * 60
                + (
                    COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES
                    - 2
                )
                * 60,
            },
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertFalse(is_alert_above_tolerance_limit(regulatory_alert))

    def test_company_compliant_no_alerts(self):
        self.assertTrue(
            compute_be_compliant(self.company, self.start, self.end, 0)
        )

    def test_company_not_compliant_max_work_day_breached(self):
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=datetime(2023, 2, 15, 3),
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=datetime(2023, 2, 15, 7),
                start_time=datetime(2023, 2, 15, 4),
                end_time=datetime(2023, 2, 15, 7),
            )

            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=datetime(2023, 2, 15, 16),
                start_time=datetime(2023, 2, 15, 8),
                end_time=datetime(2023, 2, 15, 16),
            )

            validate_mission(
                submitter=self.worker, mission=mission, for_user=self.worker
            )
        self.assertFalse(
            compute_be_compliant(self.company, self.start, self.end, 2)
        )
