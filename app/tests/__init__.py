from unittest import TestCase
from unittest.mock import patch, MagicMock
import factory
from flask.testing import FlaskClient
from enum import Enum
from datetime import date, datetime

from app import app, db, graphql_api_path
from app.models import User, Company, Employment
from app.models.employment import EmploymentRequestValidationStatus
from config import TestConfig


class BaseTest(TestCase):
    def setUp(self):
        app.config.from_object(TestConfig)
        app.testing = True

    def tearDown(self) -> None:
        db.close_all_sessions()
        all_tables = [
            "public." + str(table)
            for table in reversed(db.metadata.sorted_tables)
        ]
        db.engine.execute("TRUNCATE {} CASCADE;".format(", ".join(all_tables)))


class GraphQLTestClient(FlaskClient):
    def __init__(self, *args, mock_authentication_with_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mocked_authenticated_user = None
        self.mocked_token_verification = None
        if mock_authentication_with_user:
            self.mocked_token_verification = patch(
                "app.helpers.authentication.verify_jwt_in_request",
                new=MagicMock(return_value=None),
            )
            self.mocked_authenticated_user = patch(
                "flask_jwt_extended.utils.get_current_user",
                new=MagicMock(return_value=mock_authentication_with_user),
            )

    def __enter__(self, *args, **kwargs):
        super().__enter__(*args, **kwargs)
        if self.mocked_authenticated_user:
            self.mocked_token_verification.__enter__(*args, **kwargs)
            self.mocked_authenticated_user.__enter__(*args, **kwargs)
        return self

    def __exit__(self, *args, **kwargs):
        if self.mocked_token_verification:
            self.mocked_authenticated_user.__exit__(*args, **kwargs)
            self.mocked_token_verification.__exit__(*args, **kwargs)
        super().__exit__(*args, **kwargs)

    def post_graphql(self, query, variables=None, **kwargs):
        return self.post(
            graphql_api_path,
            json=dict(query=query, variables=variables),
            **kwargs,
        )


app.test_client_class = GraphQLTestClient


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = db.session
        strategy = "build"

    @classmethod
    def create(cls, **kwargs):
        obj = super().create(**kwargs)
        db.session.commit()
        return obj


class CompanyFactory(BaseFactory):
    class Meta:
        model = Company

    usual_name = factory.Sequence(lambda n: f"super corp {n}")
    siren = factory.Sequence(lambda n: n)


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
            )


class EmploymentFactory(BaseFactory):
    class Meta:
        model = Employment

    is_primary = True

    submitter = factory.SubFactory(UserFactory)
    reception_time = datetime(2000, 1, 1)
    validation_time = datetime(2000, 1, 1)
    validation_status = EmploymentRequestValidationStatus.APPROVED

    start_date = date(2000, 1, 1)
    company = factory.SubFactory(CompanyFactory)

    user = factory.SubFactory(UserFactory)
    has_admin_rights = False
