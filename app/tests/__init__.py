import os
from unittest import TestCase
from unittest.mock import patch, MagicMock

from flask.testing import FlaskClient
from flask_migrate import upgrade

from app import app, db, graphql_api_path, graphql_private_api_path
from config import TestConfig

MIGRATED_TEST_DB = {"value": False}


def migrate_test_db():
    app.config.from_object(TestConfig)
    if not MIGRATED_TEST_DB["value"]:
        current_dir = os.getcwd()
        os.chdir(os.path.dirname(app.root_path))
        with app.app_context():
            db.engine.execute(
                "DROP schema public CASCADE; CREATE schema public;"
            )
            upgrade()
            MIGRATED_TEST_DB["value"] = True
        os.chdir(current_dir)


class BaseTest(TestCase):
    def setUp(self):
        app.config.from_object(TestConfig)
        app.testing = True
        migrate_test_db()

    def tearDown(self) -> None:
        db.close_all_sessions()
        all_tables = [
            "public." + str(table)
            for table in reversed(db.metadata.sorted_tables)
        ]
        db.engine.execute("TRUNCATE {} CASCADE;".format(", ".join(all_tables)))


class AuthenticatedUserContext:
    def __init__(self, user=None):
        self.mocked_authenticated_user = None
        self.mocked_token_verification = None
        if user:
            self.mocked_token_verification = patch(
                "app.helpers.authentication.verify_jwt_in_request",
                new=MagicMock(return_value=None),
            )
            self.mocked_authenticated_user = patch(
                "flask_jwt_extended.utils.get_current_user",
                new=MagicMock(return_value=user),
            )

    def __enter__(self):
        if self.mocked_authenticated_user:
            self.mocked_token_verification.__enter__()
            self.mocked_authenticated_user.__enter__()
        return self

    def __exit__(self, *args):
        if self.mocked_token_verification:
            self.mocked_authenticated_user.__exit__(*args)
            self.mocked_token_verification.__exit__(*args)


class GraphQLTestClient(FlaskClient, AuthenticatedUserContext):
    def __init__(self, *args, mock_authentication_with_user=None, **kwargs):
        FlaskClient.__init__(self, *args, **kwargs)
        AuthenticatedUserContext.__init__(
            self, user=mock_authentication_with_user
        )

    def __enter__(self):
        FlaskClient.__enter__(self)
        AuthenticatedUserContext.__enter__(self)
        return self

    def __exit__(self, *args):
        AuthenticatedUserContext.__exit__(self, *args)
        FlaskClient.__exit__(self, *args)


def test_post_graphql(
    query, mock_authentication_with_user=None, variables=None, **kwargs
):
    with app.test_client(
        mock_authentication_with_user=mock_authentication_with_user
    ) as c:
        return c.post(
            graphql_api_path,
            json=dict(query=query, variables=variables),
            **kwargs,
        )


def test_post_graphql_unexposed(
    query, mock_authentication_with_user=None, variables=None, **kwargs
):
    with app.test_client(
        mock_authentication_with_user=mock_authentication_with_user
    ) as c:
        return c.post(
            graphql_private_api_path,
            json=dict(query=query, variables=variables),
            **kwargs,
        )


app.test_client_class = GraphQLTestClient
