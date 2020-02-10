import graphene
from flask import Flask
from flask_graphql import GraphQLView
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

Migrate(app, db)


from app.controllers import api
from app.helpers import cli

from app.helpers.auth import AuthMutation


class Mutations(graphene.ObjectType):
    auth = graphene.Field(
        AuthMutation, resolver=lambda root, info: AuthMutation()
    )


graphql_schema = graphene.Schema(mutation=Mutations)

app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql", schema=graphql_schema, graphiql=True
    ),
)
