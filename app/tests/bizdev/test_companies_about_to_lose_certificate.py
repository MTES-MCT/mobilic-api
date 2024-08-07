import datetime

from dateutil.relativedelta import relativedelta
from flask.ctx import AppContext

from app import app, db
from app.models import CompanyCertification
from app.seed import (
    CompanyFactory,
)
from app.jobs.emails.certificate.send_about_to_lose_certificate_emails import (
    companies_about_to_lose_certification,
    NB_MONTHS_AGO,
)
from app.tests import BaseTest


class TestCompaniesAboutToLoseCertificate(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.CURRENT_ATTRIBUTION_DATE = datetime.date.today().replace(day=1)
        self.MAX_ATTRIBUTION_DATE = (
            self.CURRENT_ATTRIBUTION_DATE - relativedelta(months=NB_MONTHS_AGO)
        )
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def get_list_companies(self):
        return companies_about_to_lose_certification(
            self.MAX_ATTRIBUTION_DATE,
            self.CURRENT_ATTRIBUTION_DATE,
            datetime.date.today(),
        )

    def certif_ok(self, attribution_date):
        db.session.add(
            CompanyCertification(
                company=self.company,
                attribution_date=attribution_date,
                expiration_date=attribution_date + relativedelta(months=6),
                be_active=True,
                be_compliant=True,
                not_too_many_changes=True,
                validate_regularly=True,
                log_in_real_time=True,
            )
        )

    def certif_ko(self, attribution_date):
        db.session.add(
            CompanyCertification(
                company=self.company,
                attribution_date=attribution_date,
                expiration_date=attribution_date + relativedelta(months=1),
                be_active=False,
                be_compliant=True,
                not_too_many_changes=True,
                validate_regularly=True,
                log_in_real_time=True,
            )
        )

    def certif_oks(self, months_ago):
        for month_ago in months_ago:
            self.certif_ok(
                datetime.date.today().replace(day=1)
                - relativedelta(months=month_ago)
            )

    def certif_kos(self, months_ago):
        for month_ago in months_ago:
            self.certif_ko(
                datetime.date.today().replace(day=1)
                - relativedelta(months=month_ago)
            )

    def test_ok_3_months_ago_ko_after(self):
        self.certif_oks([NB_MONTHS_AGO])
        self.certif_kos(range(NB_MONTHS_AGO - 1))
        res = self.get_list_companies()

        self.assertEqual(len(res), 1)

    def test_ok_3_months_ago_ok_after(self):
        self.certif_oks(range(NB_MONTHS_AGO))
        res = self.get_list_companies()

        self.assertEqual(len(res), 0)

    def test_no_certif_3_months_ago(self):
        self.certif_kos([NB_MONTHS_AGO])
        self.certif_oks(range(NB_MONTHS_AGO - 1))
        res = self.get_list_companies()

        self.assertEqual(len(res), 0)

    def test_ok_3_months_ago_ko_after_ok_today(self):
        self.certif_oks([NB_MONTHS_AGO, 0])
        self.certif_kos(range(1, NB_MONTHS_AGO - 1))
        res = self.get_list_companies()

        self.assertEqual(len(res), 0)

    def test_ok_4_months_ago_ko_after(self):
        self.certif_oks([NB_MONTHS_AGO + 1])
        self.certif_kos(range(NB_MONTHS_AGO))
        res = self.get_list_companies()

        self.assertEqual(len(res), 1)

    def test_company_was_certified_but_is_not_anymore(self):
        self.certif_oks([NB_MONTHS_AGO + 5])
        self.certif_kos(range(NB_MONTHS_AGO + 4))
        res = self.get_list_companies()

        self.assertEqual(len(res), 0)
