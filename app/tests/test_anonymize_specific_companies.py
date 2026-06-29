from app import db
from app.models import Company, Employment, User
from app.seed.factories import (
    CompanyFactory,
    EmploymentFactory,
    UserFactory,
)
from app.services.anonymization.standalone.targeted import (
    delete_specific_companies,
)
from app.tests import BaseTest


class TestDeleteSpecificCompanies(BaseTest):
    def test_empty_set_is_noop(self):
        delete_specific_companies(set())

    def test_deletes_company(self):
        company = CompanyFactory.create(usual_name="ToDelete SAS")
        company_id = company.id

        delete_specific_companies({company_id})

        db.session.expire_all()
        self.assertIsNone(Company.query.filter_by(id=company_id).one_or_none())

    def test_employments_detached_then_deleted_users_preserved(self):
        company = CompanyFactory.create(usual_name="With Employments SAS")
        user = UserFactory.create(email="kept@example.com")
        employment = EmploymentFactory.create(
            user=user, submitter=user, company=company
        )
        company_id = company.id
        user_id = user.id
        employment_id = employment.id

        delete_specific_companies({company_id})

        db.session.expire_all()
        self.assertIsNone(Company.query.filter_by(id=company_id).one_or_none())
        self.assertIsNone(
            Employment.query.filter_by(id=employment_id).one_or_none()
        )
        self.assertIsNotNone(User.query.filter_by(id=user_id).one_or_none())

    def test_test_mode_rolls_back(self):
        company = CompanyFactory.create(usual_name="ToDelete RB SAS")
        company_id = company.id

        delete_specific_companies({company_id}, test_mode=True)

        db.session.expire_all()
        self.assertIsNotNone(
            Company.query.filter_by(id=company_id).one_or_none()
        )
