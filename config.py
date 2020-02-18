from datetime import timedelta
import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost:5432/mobilic"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=3)
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=5)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-little-secret")
    DISABLE_AUTH_FOR_TESTING = False
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    MAXIMUM_TIME_AHEAD_FOR_EVENT = timedelta(minutes=5)


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic-test"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProdConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=100)
