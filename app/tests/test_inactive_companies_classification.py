from datetime import datetime, timedelta

from app import db
from app.models import Mission
from app.seed.factories import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.helpers import AuthenticatedUserContext
from app.services.anonymization.user_related.classifier import UserClassifier
from app.tests import BaseTest


class TestInactiveCompaniesClassification(BaseTest):
    """
    A company is inactive (anonymization scope) only if it has no live
    employment AND no mission since the cutoff date. Companies keeping
    attached employees or logging missions must stay out of scope.
    """

    def setUp(self):
        super().setUp()
        self.cutoff_date = datetime.now() - timedelta(days=1)
        self.user = UserFactory.create()

    def _make_old_company(self, siren):
        company = CompanyFactory.create(
            usual_name=f"Company {siren}", siren=siren
        )
        # Column defaults are set at insert time: age the row explicitly
        db.session.execute(
            "UPDATE company SET creation_time = :creation_time WHERE id = :id",
            {
                "creation_time": self.cutoff_date - timedelta(days=365),
                "id": company.id,
            },
        )
        return company

    def _attach_employment(self, company, end_date=None):
        return EmploymentFactory.create(
            user=self.user,
            company=company,
            start_date=(datetime.now() - timedelta(days=730)).date(),
            end_date=end_date,
            has_admin_rights=False,
            submitter=self.user,
            validation_status="approved",
            reception_time=datetime.now(),
        )

    def _log_recent_mission(self, company):
        with AuthenticatedUserContext(user=self.user):
            mission = Mission(
                company=company,
                creation_time=datetime.now(),
                reception_time=datetime.now(),
                submitter=self.user,
            )
            db.session.add(mission)
            db.session.commit()

    def _inactive_companies(self):
        return set(UserClassifier(self.cutoff_date)._get_inactive_companies())

    def test_company_with_only_ended_employments_is_inactive(self):
        company = self._make_old_company("111111111")
        self._attach_employment(
            company, end_date=(datetime.now() - timedelta(days=30)).date()
        )
        db.session.commit()

        self.assertIn(company.id, self._inactive_companies())

    def test_company_with_live_employment_is_not_inactive(self):
        company = self._make_old_company("222222222")
        self._attach_employment(company, end_date=None)
        db.session.commit()

        self.assertNotIn(company.id, self._inactive_companies())

    def test_company_with_recent_mission_is_not_inactive(self):
        company = self._make_old_company("333333333")
        self._attach_employment(
            company, end_date=(datetime.now() - timedelta(days=30)).date()
        )
        db.session.commit()
        self._log_recent_mission(company)

        self.assertNotIn(company.id, self._inactive_companies())
