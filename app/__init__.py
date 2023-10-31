import os

import sentry_sdk
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask
from flask_apispec.extension import FlaskApiSpec
from flask_compress import Compress
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

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=os.environ.get("SENTRY_SAMPLE_RATE", 0),
)
app = Flask(__name__)

Compress(app)
# See list of possible settings at https://pypi.org/project/Flask-Compress/1.13/
app.config.update({"COMPRESS_MIN_SIZE": 100})
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

siren_api_client = SirenAPIClient(app.config["SIREN_API_KEY"])

for name, filter in JINJA_CUSTOM_FILTERS.items():
    app.template_filter(name)(filter)

from app.helpers.mail import mailer


db = SQLAlchemyWithStrongRefSession(
    app, session_options={"expire_on_commit": False}
)

if app.config["ECHO_DB_QUERIES"]:
    db.engine.echo = True

Migrate(app, db)

CORS(app)

from app.helpers.graphql import CustomGraphQLView
from app.controllers import (
    graphql_schema,
    private_graphql_schema,
    protected_graphql_schema,
)
from app.helpers import logging

from . import commands


@app.before_first_request
def configure_app():
    if MOBILIC_ENV == "prod":
        db.engine.dispose()


graphql_api_path = "/graphql"
graphql_private_api_path = "/unexposed"
graphql_protected_api_path = "/protected"


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

app.add_url_rule(
    graphql_protected_api_path,
    view_func=CustomGraphQLView.as_view(
        "protected", schema=protected_graphql_schema, graphiql=True
    ),
)


from app.helpers.oauth import oauth_blueprint

app.register_blueprint(oauth_blueprint, url_prefix="/oauth")

from app.controllers.control import control_blueprint

app.register_blueprint(control_blueprint, url_prefix="/control")


from app.controllers.misc import *
from app.controllers.certificate import *


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
