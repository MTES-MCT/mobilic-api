from datetime import date

from flask.ctx import AppContext

from app import app
from app.domain.certificate_criteria import (
    certificate_expiration,
    compute_company_certification,
)
from app.helpers.time import previous_month_period
from app.seed.factories import CompanyFactory
from app.tests import BaseTest


class TestCertificateCriteria(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_certificate_expiration(self):
        expiration_date = certificate_expiration(date(2023, 3, 28))
        self.assertEqual(expiration_date, date(2023, 8, 31))

    def test_compute_company_certification(self):
        start, end = previous_month_period(date(2023, 3, 28))
        compute_company_certification(
            company=self.company, start=start, end=end, today=date.today()
        )
        # should not fail
