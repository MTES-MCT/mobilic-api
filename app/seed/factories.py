from datetime import datetime, date

import factory

from app import db
from app.models import User, Employment, Company
from app.models.employment import EmploymentRequestValidationStatus


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = db.session
        strategy = "build"

    @classmethod
    def create(cls, **kwargs):
        obj = super().create(**kwargs)
        db.session.commit()
        return obj


class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"test{n}@test.test")
    password = "mybirthday"
    first_name = "Moby"
    last_name = "Lick"
    has_activated_email = True
    has_confirmed_email = True

    @factory.post_generation
    def post(obj, create, extracted, **kwargs):
        if "company" in kwargs:
            generate_func = (
                EmploymentFactory.create if create else EmploymentFactory.build
            )
            generate_func(
                company=kwargs["company"],
                user=obj,
                submitter=obj,
                has_admin_rights=kwargs.get("has_admin_rights", False),
                start_date=kwargs.get("start_date", date(2000, 1, 1)),
                end_date=kwargs.get("end_date", None),
            )


class CompanyFactory(BaseFactory):
    class Meta:
        model = Company

    usual_name = factory.Sequence(lambda n: f"super corp {n}")
    siren = factory.Sequence(lambda n: n)


class EmploymentFactory(BaseFactory):
    class Meta:
        model = Employment

    submitter = factory.SubFactory(UserFactory)
    reception_time = datetime(2000, 1, 1)
    validation_time = datetime(2000, 1, 1)
    validation_status = EmploymentRequestValidationStatus.APPROVED

    start_date = date(2000, 1, 1)
    company = factory.SubFactory(CompanyFactory)

    user = factory.SubFactory(UserFactory)
    has_admin_rights = False
