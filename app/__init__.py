from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from config import Config


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

Migrate(app, db)

from app import models
from app.controllers import api
from app.helpers import cli

from app.helpers.auth import auth

app.register_blueprint(auth, url_prefix="/auth")
