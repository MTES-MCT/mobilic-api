from flask import Flask
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_cors import CORS
import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from app.helpers.db import SQLAlchemyWithStrongRefSession
from app.helpers.siren import SirenAPIClient

app = Flask(__name__)

env = os.environ.get("MOBILIC_ENV", "dev")
app.config.from_object(getattr(config, f"{env.capitalize()}Config"))

siren_api_client = SirenAPIClient(app.config["SIREN_API_KEY"])

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
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True, batch=True
    ),
)

app.add_url_rule(
    graphql_private_api_path,
    view_func=GraphQLView.as_view(
        "unexposed", schema=private_graphql_schema, graphiql=False
    ),
)


@app.route("/debug-sentry")
def trigger_error():
    division_by_zero = 1 / 0
