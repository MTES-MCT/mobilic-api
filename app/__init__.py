from flask import Flask
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS


from config import Config


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

Migrate(app, db)

CORS(app)

from app.helpers import cli
from app.controllers import graphql_schema
from app.helpers.admin import admin


graphql_api_path = "/api/graphql"


app.add_url_rule(
    graphql_api_path,
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True
    ),
)
