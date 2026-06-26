from datetime import date, datetime

from flask.ctx import AppContext

from app import db, app
from app.domain.regulations import get_default_business
from app.domain.regulations_per_day import (
    EXTRA_NOT_ENOUGH_BREAK,
    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
    NATINF_11292,
    NATINF_32083,
)
from app.domain.regulatory_alerts_summary import (
    MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE,
    has_any_regulation_computation,
    get_regulatory_alerts_summary,
)
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation, RegulatoryAlert, RegulationCheck
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.factories import ActivityFactory, MissionFactory
from app.tests import BaseTest
from app.tests.helpers import init_regulation_checks_data, init_businesses_data


class TestRegulatoryAlertsSummary(BaseTest):
    def setUp(self):
        super().setUp()

        init_regulation_checks_data()
        init_businesses_data()

        user = UserFactory.create(
            password="password",
        )
        self.user = user
        self.business = get_default_business()
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_has_any_regulation_computation(self):
        db.session.add(
            RegulationComputation(
                day=date(2025, 4, 10),
                submitter_type=SubmitterType.EMPLOYEE,
                user_id=self.user.id,
            )
        )
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.EMPLOYEE,
                user_id=self.user.id,
            )
        )

        self.assertFalse(
            has_any_regulation_computation(month=date(2025, 4, 1), user_ids=[])
        )
        self.assertFalse(
            has_any_regulation_computation(
                month=date(2025, 4, 1), user_ids=[self.user.id]
            )
        )
        self.assertTrue(
            has_any_regulation_computation(
                month=date(2025, 5, 1), user_ids=[self.user.id]
            )
        )

    def test_summary_object(self):
        db.session.add(
            RegulationComputation(
                day=date(2025, 4, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )

        not_enough_break_check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
        ).first()
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 10),
                user_id=self.user.id,
                regulation_check=not_enough_break_check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
                extra={
                    EXTRA_NOT_ENOUGH_BREAK: True,
                    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME: True,
                },
            )
        )
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 4, 10),
                user_id=self.user.id,
                regulation_check=not_enough_break_check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
                extra={
                    EXTRA_NOT_ENOUGH_BREAK: False,
                    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME: True,
                },
            )
        )

        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1), user_ids=[self.user.id]
        )
        self.assertEqual(1, summary.total_nb_alerts_previous_month)
        self.assertEqual(2, summary.total_nb_alerts)

    def _seed_alert_with_companies(
        self, current_siren, other_siren, with_other_activity=True
    ):
        """Set up an alert on a fixed day and (optionally) seed activity
        for the same user in another company so the multi-employer flag
        can be exercised."""
        alert_day = date(2025, 5, 12)

        current_company = CompanyFactory.create(
            usual_name="Current", siren=current_siren
        )
        other_company = CompanyFactory.create(
            usual_name="Other", siren=other_siren
        )
        EmploymentFactory.create(
            company=current_company, submitter=self.user, user=self.user
        )

        db.session.add(
            RegulationComputation(
                day=alert_day,
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ).first()
        db.session.add(
            RegulatoryAlert(
                day=alert_day,
                user_id=self.user.id,
                regulation_check=check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
            )
        )

        if with_other_activity:
            mission = MissionFactory.create(
                company_id=other_company.id,
                submitter_id=self.user.id,
                reception_time=datetime(2025, 5, 12, 8, 0, 0),
            )
            ActivityFactory.create(
                mission=mission,
                user=self.user,
                submitter=self.user,
                type=ActivityType.DRIVE,
                reception_time=datetime(2025, 5, 12, 8, 0, 0),
                start_time=datetime(2025, 5, 12, 8, 0, 0),
                last_update_time=datetime(2025, 5, 12, 11, 0, 0),
            )
        db.session.commit()

        return current_company, alert_day

    def _get_day_detail(self, summary, alert_type, alert_day, user_id):
        for group in summary.daily_alerts:
            if group.alerts_type != alert_type:
                continue
            for d in group.day_details:
                if d.day == alert_day and d.user_id == user_id:
                    return d
        return None

    def test_other_company_relation_company_when_siren_differs(self):
        """SIREN différent → relation 'company'."""
        current, alert_day = self._seed_alert_with_companies(
            current_siren="111111111", other_siren="222222222"
        )
        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1),
            user_ids=[self.user.id],
            company_id=current.id,
        )
        detail = self._get_day_detail(
            summary,
            RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
            alert_day,
            self.user.id,
        )
        self.assertIsNotNone(detail)
        self.assertEqual("company", detail.other_company_relation)

    def test_other_company_relation_establishment_when_siren_matches(self):
        """Même SIREN → relation 'establishment'."""
        current, alert_day = self._seed_alert_with_companies(
            current_siren="333333333", other_siren="333333333"
        )
        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1),
            user_ids=[self.user.id],
            company_id=current.id,
        )
        detail = self._get_day_detail(
            summary,
            RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
            alert_day,
            self.user.id,
        )
        self.assertIsNotNone(detail)
        self.assertEqual("establishment", detail.other_company_relation)

    def test_other_company_relation_none_when_only_current_activity(self):
        """Pas d'activité dans une autre company → relation None."""
        current, alert_day = self._seed_alert_with_companies(
            current_siren="444444444",
            other_siren="555555555",
            with_other_activity=False,
        )
        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1),
            user_ids=[self.user.id],
            company_id=current.id,
        )
        detail = self._get_day_detail(
            summary,
            RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
            alert_day,
            self.user.id,
        )
        self.assertIsNotNone(detail)
        self.assertIsNone(detail.other_company_relation)

    def test_window_mode_restricts_alerts_to_range(self):
        """When from_date/to_date are provided, only alerts within that
        window are loaded — the homepage uses this mode to fetch a single
        week instead of a full month."""
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 5),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ).first()
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 5),
                user_id=self.user.id,
                regulation_check=check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
            )
        )
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 20),
                user_id=self.user.id,
                regulation_check=check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
            )
        )
        db.session.commit()

        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1),
            user_ids=[self.user.id],
            from_date=date(2025, 5, 5),
            to_date=date(2025, 5, 12),
        )
        self.assertEqual(1, summary.total_nb_alerts)
        self.assertEqual(0, summary.total_nb_alerts_previous_month)

    def test_regulatory_alerts_summary_splits_day_night(self):
        """
        MAXIMUM_WORK_DAY_TIME alerts must be split in two AlertsGroup
        based on extra['sanction_code']: NATINF 11292 (day) and
        NATINF 32083 (night) appear under distinct alerts_type values.
        Other daily checks must coexist without being affected by the split.
        """
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        max_work_check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ).first()
        min_rest_check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
        ).first()

        for d in (5, 6):
            db.session.add(
                RegulatoryAlert(
                    day=date(2025, 5, d),
                    user_id=self.user.id,
                    regulation_check=max_work_check,
                    submitter_type=SubmitterType.ADMIN,
                    business=self.business,
                    extra={"sanction_code": NATINF_11292},
                )
            )
        for d in (7, 8, 9):
            db.session.add(
                RegulatoryAlert(
                    day=date(2025, 5, d),
                    user_id=self.user.id,
                    regulation_check=max_work_check,
                    submitter_type=SubmitterType.ADMIN,
                    business=self.business,
                    extra={"sanction_code": NATINF_32083},
                )
            )
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 10),
                user_id=self.user.id,
                regulation_check=min_rest_check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
                extra={},
            )
        )

        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1), user_ids=[self.user.id]
        )
        daily = {g.alerts_type: g for g in summary.daily_alerts}

        self.assertIn(RegulationCheckType.MAXIMUM_WORK_DAY_TIME, daily)
        self.assertIn(MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE, daily)
        self.assertEqual(
            2, daily[RegulationCheckType.MAXIMUM_WORK_DAY_TIME].nb_alerts
        )
        self.assertEqual(3, daily[MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE].nb_alerts)
        self.assertEqual(6, summary.total_nb_alerts)

    def test_legacy_alerts_without_sanction_code_count_as_day(self):
        """
        Backward compatibility: alerts in DB without 'sanction_code'
        in extra (e.g. legacy data) keep being grouped as day alerts.
        """
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.user.id,
            )
        )
        max_work_check = RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ).first()
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 5),
                user_id=self.user.id,
                regulation_check=max_work_check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
                extra={"work_range_in_seconds": 50000},
            )
        )

        summary = get_regulatory_alerts_summary(
            month=date(2025, 5, 1), user_ids=[self.user.id]
        )
        daily = {g.alerts_type: g for g in summary.daily_alerts}
        self.assertEqual(
            1, daily[RegulationCheckType.MAXIMUM_WORK_DAY_TIME].nb_alerts
        )
        self.assertEqual(0, daily[MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE].nb_alerts)
