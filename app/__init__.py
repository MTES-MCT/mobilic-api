from flask import Flask, g, request
from flask_httpauth import HTTPBasicAuth
from flask_migrate import Migrate
from flask_cors import CORS
import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from app.helpers.db import SQLAlchemyWithStrongRefSession
from app.helpers.mail import Mailer
from app.helpers.siren import SirenAPIClient

app = Flask(__name__)

env = os.environ.get("MOBILIC_ENV", "dev")
app.config.from_object(getattr(config, f"{env.capitalize()}Config"))

siren_api_client = SirenAPIClient(app.config["SIREN_API_KEY"])
mailer = Mailer(app.config)

if app.config["SENTRY_URL"]:
    sentry_sdk.init(
        dsn=app.config["SENTRY_URL"],
        integrations=[FlaskIntegration()],
        environment=app.config["SENTRY_ENVIRONMENT"],
    )

db = SQLAlchemyWithStrongRefSession(
    app, session_options={"expire_on_commit": False}
)

if app.config["ECHO_DB_QUERIES"]:
    db.engine.echo = True

Migrate(app, db)

CORS(app)

from app.helpers import cli
from app.helpers.graphql import CustomGraphQLView
from app.controllers import graphql_schema, private_graphql_schema
from app.helpers.admin import admin
from app.helpers import logging


@app.before_first_request
def configure_app():
    if env == "prod":
        db.engine.dispose()


graphql_api_path = "/graphql"
graphql_private_api_path = "/unexposed"


app.add_url_rule(
    graphql_api_path,
    view_func=CustomGraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True, batch=True
    ),
)

app.add_url_rule(
    graphql_private_api_path,
    view_func=CustomGraphQLView.as_view(
        "unexposed", schema=private_graphql_schema, graphiql=False
    ),
)

from app.helpers.oauth import oauth_blueprint

app.register_blueprint(oauth_blueprint, url_prefix="/oauth")


@app.route("/debug-sentry")
def trigger_error():
    division_by_zero = 1 / 0


if env == "prod":
    auth = HTTPBasicAuth()

    @auth.verify_password
    def verify_password(username, password):
        if (
            username
            and username == os.environ.get("MOBILIC_ADMIN_USER")
            and password
            and password == os.environ.get("MOBILIC_ADMIN_PASSWORD")
        ):
            return True

    @app.route("/services/update-stat-spreadsheet", methods=["POST"])
    @auth.login_required()
    def compute_usage_stats():
        from app.services.compute_usage_stats import (
            compute_and_add_usage_stats_snapshot,
        )

        success = False
        try:
            compute_and_add_usage_stats_snapshot()
            success = True
        except Exception as e:
            app.logger.exception(e)

        return (
            "La spreadsheet a été mise à jour"
            if success
            else "La spreadsheet n'a pas pu être mise à jour à cause d'erreurs.",
            200 if success else 500,
        )
