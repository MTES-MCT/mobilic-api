from datetime import timedelta
import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost:5432/mobilic"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ECHO_DB_QUERIES = False
    MINIMUM_ACTIVITY_DURATION = timedelta(seconds=0)
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=5)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-little-secret")
    DISABLE_AUTH_FOR_TESTING = False
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    MAXIMUM_TIME_AHEAD_FOR_EVENT = timedelta(minutes=5)
    ALLOW_INSECURE_IMPERSONATION = False
    SENTRY_URL = os.environ.get("SENTRY_URL")
    SENTRY_ENVIRONMENT = "dev"
    SIREN_API_KEY = os.environ.get("SIREN_API_KEY")
    FRONTEND_URL = os.environ.get("FRONTEND_URL")
    MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY")
    MAILJET_API_SECRET = os.environ.get("MAILJET_API_SECRET")
    FC_CLIENT_ID = os.environ.get("FC_CLIENT_ID")
    FC_CLIENT_SECRET = os.environ.get("FC_CLIENT_SECRET")
    FC_URL = os.environ.get(
        "FC_URL", "https://fcp.integ01.dev-franceconnect.fr"
    )
    EMAIL_ACTIVATION_TOKEN_EXPIRATION = timedelta(days=7)


class DevConfig(Config):
    ALLOW_INSECURE_IMPERSONATION = True
    ECHO_DB_QUERIES = os.environ.get("ECHO_DB_QUERIES", False)
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


class StagingConfig(Config):
    SENTRY_ENVIRONMENT = "staging"
    pass


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic-test"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProdConfig(Config):
    SENTRY_ENVIRONMENT = "prod"
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=100)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)


class SandboxConfig(Config):
    SENTRY_ENVIRONMENT = "sandbox"
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=100)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)
