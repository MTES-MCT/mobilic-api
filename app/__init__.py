from flask import Flask
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

Migrate(app, db)


from app.helpers import cli
from app.controllers import graphql_schema


app.add_url_rule(
    "/api",
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True
    ),
)
