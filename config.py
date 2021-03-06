from datetime import timedelta
import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost:5432/mobilic"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ECHO_DB_QUERIES = False
    MINIMUM_ACTIVITY_DURATION = timedelta(seconds=0)
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=2)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-little-secret")
    DISABLE_AUTH_FOR_TESTING = False
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    OVH_LDP_TOKEN = os.environ.get("OVH_LDP_TOKEN")
    MAXIMUM_TIME_AHEAD_FOR_EVENT = timedelta(minutes=5)
    SENTRY_URL = os.environ.get("SENTRY_URL")
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
    SLACK_LOG_CHANNEL = os.environ.get("SLACK_LOG_CHANNEL", "#mobilic-alerts")
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_COOKIE_NAME = "at"
    JWT_ACCESS_COOKIE_PATH = "/api"
    JWT_REFRESH_COOKIE_NAME = "rt"
    JWT_REFRESH_COOKIE_PATH = "/api/token"
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_LIFETIME = timedelta(days=365)
    RESET_PASSWORD_TOKEN_EXPIRATION = timedelta(days=1)


class DevConfig(Config):
    ECHO_DB_QUERIES = os.environ.get("ECHO_DB_QUERIES", False)
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    JWT_COOKIE_SECURE = False


class StagingConfig(Config):
    pass


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic-test"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProdConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=100)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)


class SandboxConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(days=1)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)
