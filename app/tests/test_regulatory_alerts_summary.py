from datetime import date

from flask.ctx import AppContext

from app import db, app
from app.domain.regulations import get_default_business
from app.domain.regulations_per_day import (
    EXTRA_NOT_ENOUGH_BREAK,
    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
)
from app.domain.regulatory_alerts_summary import (
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
