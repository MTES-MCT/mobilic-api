from flask import Flask, redirect
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

import config


app = Flask(__name__)

env = os.environ.get("MOBILIC_ENV", "")
app.config.from_object(getattr(config, f"{env.capitalize()}Config"))

db = SQLAlchemy(app)

Migrate(app, db)

CORS(app)

from app.helpers import cli
from app.controllers import graphql_schema
from app.helpers.admin import admin
from app.helpers import logging


graphql_api_path = "/graphql"


@app.route("/api/<path:u_path>")
def redirect_to_new_routes(u_path):
    return redirect(f"/{u_path}")


app.add_url_rule(
    graphql_api_path,
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True
    ),
)
