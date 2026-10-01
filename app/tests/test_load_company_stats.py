from datetime import datetime

from app import db
from app.models.company_stats import CompanyStats
from app.models.mission_validation import MissionValidation
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import MissionFactory
from app.services.load_company_stats import (
    load_company_stats,
    get_first_mission_validation_by_admin_date,
)
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


class TestGetFirstMissionValidationByAdminDate(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.employee = UserFactory.create(
            post__company=self.company,
        )

    def _create_mission(self, submitter=None):
        submitter = submitter or self.employee
        return MissionFactory.create(
            company_id=self.company.id,
            submitter_id=submitter.id,
            reception_time=datetime.now(),
        )

    def _add_validation(self, mission, user, submitter, is_admin, is_auto):
        validation = MissionValidation(
            mission=mission,
            user=user,
            submitter=submitter,
            is_admin=is_admin,
            is_auto=is_auto,
            reception_time=datetime.now(),
        )
        db.session.add(validation)
        db.session.commit()
        return validation

    def test_auto_validated_mission_for_employee_counts(self):
        # The admin-tier auto-validation job validated an employee's
        # mission because nobody reviewed it in time: this is a genuine
        # sign of admin activation, even though there is no submitter.
        mission = self._create_mission()
        self._add_validation(
            mission,
            user=self.employee,
            submitter=None,
            is_admin=True,
            is_auto=True,
        )

        result = get_first_mission_validation_by_admin_date(self.company.id)

        self.assertIsNotNone(result)

    def test_admin_auto_validating_own_mission_does_not_count(self):
        # The admin drives their own missions and never validates anything
        # manually: their own missions eventually reach the admin-tier
        # auto-validation queue too. That should NOT count as evidence the
        # admin is managing a team.
        mission = self._create_mission(submitter=self.admin)
        self._add_validation(
            mission,
            user=self.admin,
            submitter=None,
            is_admin=True,
            is_auto=True,
        )

        result = get_first_mission_validation_by_admin_date(self.company.id)

        self.assertIsNone(result)

    def test_manual_admin_validation_for_employee_counts(self):
        mission = self._create_mission()
        self._add_validation(
            mission,
            user=self.employee,
            submitter=self.admin,
            is_admin=True,
            is_auto=False,
        )

        result = get_first_mission_validation_by_admin_date(self.company.id)

        self.assertIsNotNone(result)

    def test_manual_admin_validation_for_self_does_not_count(self):
        mission = self._create_mission(submitter=self.admin)
        self._add_validation(
            mission,
            user=self.admin,
            submitter=self.admin,
            is_admin=True,
            is_auto=False,
        )

        result = get_first_mission_validation_by_admin_date(self.company.id)

        self.assertIsNone(result)
