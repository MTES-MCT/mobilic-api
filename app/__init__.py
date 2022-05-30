import logging

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from elasticapm.contrib.flask import ElasticAPM
from flask import Flask
from flask_apispec import FlaskApiSpec
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.exceptions import HTTPException

import config
from app.helpers.db import SQLAlchemyWithStrongRefSession
from app.helpers.errors import MobilicError
from app.helpers.request_parser import CustomRequestParser
from app.helpers.siren import SirenAPIClient
from app.templates.filters import JINJA_CUSTOM_FILTERS
from config import MOBILIC_ENV

app = Flask(__name__)
app.config.update(
    {
        "APISPEC_SPEC": APISpec(
            title="Mobilic",
            version="v1",
            openapi_version="3.0.0",
            plugins=[MarshmallowPlugin()],
        ),
        "APISPEC_WEBARGS_PARSER": CustomRequestParser(),
    }
)

docs = FlaskApiSpec(app)

app.config.from_object(getattr(config, f"{MOBILIC_ENV.capitalize()}Config"))

apm = ElasticAPM(app, logging=logging.ERROR)
siren_api_client = SirenAPIClient(app.config["SIREN_API_KEY"])

for name, filter in JINJA_CUSTOM_FILTERS.items():
    app.template_filter(name)(filter)

from app.helpers.mail import mailer


if app.config["SENTRY_URL"]:
    from app.helpers.sentry import setup_sentry

    setup_sentry()

db = SQLAlchemyWithStrongRefSession(
    app, session_options={"expire_on_commit": False}
)

if app.config["ECHO_DB_QUERIES"]:
    db.engine.echo = True

Migrate(app, db)

from app.helpers.graphql import CustomGraphQLView
from app.controllers import graphql_schema, private_graphql_schema
from app.helpers import logging

from . import commands


@app.before_first_request
def configure_app():
    if MOBILIC_ENV == "prod":
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

from app.controllers.control import control_blueprint

app.register_blueprint(control_blueprint, url_prefix="/control")


@app.route("/debug-sentry")
def trigger_error():
    division_by_zero = 1 / 0


from app.services import service_decorator


@app.route("/services/update-stat-spreadsheet", methods=["POST"])
@service_decorator
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


from app.controllers.misc import *


@app.route("/services/send-onboarding-emails", methods=["POST"])
@service_decorator
def send_onboarding_emails():
    from app.services.send_onboarding_emails import send_onboarding_emails
    from datetime import date

    send_onboarding_emails(date.today())

    return "C'est fait", 200


@app.errorhandler(MobilicError)
def handle_error(error):
    app.logger.exception(error)
    error.extensions.pop("code")
    error_payload = {"error": error.message, "error_code": error.code}
    if error.extensions:
        error_payload["details"] = error.extensions
    return jsonify(error_payload), error.http_status_code


@app.errorhandler(HTTPException)
def handle_error(error):
    app.logger.exception(error)
    return (
        jsonify(
            {
                "error": error.description,
                "error_code": error.name.upper().replace(" ", "_"),
            }
        ),
        error.code,
    )
