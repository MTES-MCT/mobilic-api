import math
from datetime import date

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    compute_compliancy,
    COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE,
)
from app.domain.regulations import get_default_business
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import previous_month_period
from app.models import RegulatoryAlert, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.seed import (
    CompanyFactory,
    UserFactory,
)
from app.tests import BaseTest
from app.tests.helpers import init_regulation_checks_data, init_businesses_data


class TestCertificateBeCompliant(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()
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

    def test_company_compliant_no_alerts(self):
        self.assertEqual(
            compute_compliancy(self.company, self.start, self.end, 2), 6
        )

    def test_compliancy_max_allowed_percentage(self):
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ).first(),
            business=get_default_business(),
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        nb_activities_to_make_one_alert_ok = math.ceil(
            1 / (COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE / 100.0)
        )

        self.assertEqual(
            compute_compliancy(
                self.company,
                self.start,
                self.end,
                nb_activities_to_make_one_alert_ok + 1,
            ),
            6,
        )
        self.assertEqual(
            compute_compliancy(
                self.company,
                self.start,
                self.end,
                nb_activities_to_make_one_alert_ok - 1,
            ),
            5,
        )

    def test_compliancy_different_scores(self):
        self.assertEqual(
            compute_compliancy(self.company, self.start, self.end, 50), 6
        )
        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ).first(),
            business=get_default_business(),
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertEqual(
            compute_compliancy(self.company, self.start, self.end, 50), 5
        )

        regulatory_alert = RegulatoryAlert(
            day="2023-02-15",
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.worker,
            regulation_check=RegulationCheck.query.filter(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK
            ).first(),
            business=get_default_business(),
        )
        db.session.add(regulatory_alert)
        db.session.commit()

        self.assertEqual(
            compute_compliancy(self.company, self.start, self.end, 50), 4
        )
