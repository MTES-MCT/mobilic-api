from app import db
from app.models.company_stats import CompanyStats
from app.seed import CompanyFactory
from app.services.load_company_stats import load_company_stats
from app.tests import BaseTest


class TestLoadCompanyStats(BaseTest):
    def get_stats_for_company(self, company_id):
        return CompanyStats.query.filter(
            CompanyStats.company_id == company_id
        ).one_or_none()

    def setUp(self):
        super().setUp()

    def test_new_company(self):
        new_company = CompanyFactory.create()

        load_company_stats()
        db.session.expire_all()

        company_stats = self.get_stats_for_company(new_company.id)
        self.assertIsNotNone(company_stats)
        self.assertEqual(
            company_stats.company_creation_date,
            new_company.creation_time.date(),
        )

    def test_existing_company(self):
        existing_company = CompanyFactory.create()
        existing_company_stats = CompanyStats(
            company_id=existing_company.id,
            company_creation_date=existing_company.creation_time,
            first_employee_invitation_date=existing_company.creation_time,
        )
        db.session.add(existing_company_stats)
        db.session.commit()

        load_company_stats()
        db.session.expire_all()

        company_stats = self.get_stats_for_company(existing_company.id)
        self.assertIsNotNone(company_stats)
