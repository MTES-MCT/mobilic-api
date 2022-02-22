import os
import sys
from unittest import TestCase, TestLoader, TextTestRunner
from unittest.mock import patch, MagicMock

from flask.testing import FlaskClient
from flask_migrate import upgrade

from app import app, db, graphql_api_path, graphql_private_api_path
from app.seed import AuthenticatedUserContext
from config import TestConfig

MIGRATED_TEST_DB = {"value": False}


def run_tests_from_cli():
    app.config.from_object(TestConfig)
    root_project_path = os.path.dirname(app.root_path)
    test_suite = TestLoader().discover(
        os.path.join(app.root_path, "tests"),
        pattern="test_*.py",
        top_level_dir=root_project_path,
    )
    result = TextTestRunner(verbosity=3).run(test_suite)
    if result.wasSuccessful():
        sys.exit(0)
    sys.exit(1)


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


app.test_client_class = GraphQLTestClient
