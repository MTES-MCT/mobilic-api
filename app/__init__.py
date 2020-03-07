from flask import Flask
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_cors import CORS
import os

import config
from app.helpers.db import SQLAlchemyWithStrongRefSession

app = Flask(__name__)

env = os.environ.get("MOBILIC_ENV", "")
app.config.from_object(getattr(config, f"{env.capitalize()}Config"))

db = SQLAlchemyWithStrongRefSession(
    app, session_options={"expire_on_commit": False}
)

Migrate(app, db)

CORS(app)

from app.helpers import cli
from app.controllers import graphql_schema
from app.helpers.admin import admin
from app.helpers import logging


@app.before_first_request
def configure_app():
    if env == "prod":
        db.engine.dispose()


graphql_api_path = "/graphql"


app.add_url_rule(
    graphql_api_path,
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True
    ),
)

app.add_url_rule(
    "/api" + graphql_api_path,
    view_func=GraphQLView.as_view(
        "old_graphql", schema=graphql_schema, graphiql=True
    ),
)
