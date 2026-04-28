from datetime import date

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
from app.models.regulation_check import RegulationCheckType
from app.seed import UserFactory
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

    def test_regulatory_alerts_summary_splits_day_night(self):
        """
        MAXIMUM_WORK_DAY_TIME alerts must be split in two AlertsGroup
        based on extra['sanction_code']: NATINF 11292 (day) and
        NATINF 32083 (night) appear under distinct alerts_type values.
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

        # 2 day alerts (NATINF 11292)
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
        # 3 night alerts (NATINF 32083)
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
        # Total stays the sum (no double-counting)
        self.assertEqual(5, summary.total_nb_alerts)

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

    def test_total_nb_alerts_with_mixed_day_night_and_other_checks(self):
        """
        AC10 — total_nb_alerts must remain the simple sum of all alerts
        (day + night + other daily checks), with no double counting from
        the day/night split.
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

        # 1 day alert (NATINF 11292) + 2 night alerts (NATINF 32083)
        # + 1 unrelated daily check alert.
        db.session.add(
            RegulatoryAlert(
                day=date(2025, 5, 5),
                user_id=self.user.id,
                regulation_check=max_work_check,
                submitter_type=SubmitterType.ADMIN,
                business=self.business,
                extra={"sanction_code": NATINF_11292},
            )
        )
        for d in (6, 7):
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
                day=date(2025, 5, 8),
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

        self.assertEqual(4, summary.total_nb_alerts)
