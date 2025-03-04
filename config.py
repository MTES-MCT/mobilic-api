import json
from datetime import timedelta, datetime
from dotenv import load_dotenv
import os

if os.environ.get("DOTENV_FILE", False):
    load_dotenv(os.environ.get("DOTENV_FILE"))

MOBILIC_ENV = os.environ.get("MOBILIC_ENV", "dev")

CGU_INITIAL_RELASE_DATE = datetime(2022, 1, 1)
CGU_INITIAL_VERSION = "v1.0"


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://mobilic:mobilic@localhost:5432/mobilic",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ECHO_DB_QUERIES = False
    MINIMUM_ACTIVITY_DURATION = timedelta(seconds=0)
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=5)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-little-secret")
    DISABLE_PASSWORD_CHECK = os.environ.get("DISABLE_PASSWORD_CHECK", False)
    MATTERMOST_WEBHOOK = os.environ.get("MATTERMOST_WEBHOOK")
    OVH_LDP_TOKEN = os.environ.get("OVH_LDP_TOKEN")
    MAXIMUM_TIME_AHEAD_FOR_EVENT = timedelta(minutes=5)
    SIREN_API_KEY = os.environ.get("SIREN_API_KEY")
    FRONTEND_URL = os.environ.get("FRONTEND_URL")
    MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY")
    MAILJET_API_SECRET = os.environ.get("MAILJET_API_SECRET")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
    FC_CLIENT_ID = os.environ.get("FC_CLIENT_ID")
    FC_CLIENT_SECRET = os.environ.get("FC_CLIENT_SECRET")
    FC_URL = os.environ.get(
        "FC_URL", "https://fcp.integ01.dev-franceconnect.fr"
    )
    AC_CLIENT_ID = os.environ.get("AC_CLIENT_ID")
    AC_CLIENT_SECRET = os.environ.get("AC_CLIENT_SECRET")
    AC_AUTHORIZE_URL = os.environ.get("AC_AUTHORIZE_URL")
    AC_TOKEN_URL = os.environ.get("AC_TOKEN_URL")
    AC_LOGOUT_URL = os.environ.get("AC_LOGOUT_URL")
    AC_USER_INFO_URL = os.environ.get("AC_USER_INFO_URL")
    AC_JWKS_INFO = os.environ.get("AC_JWKS_INFO")
    EMAIL_ACTIVATION_TOKEN_EXPIRATION = timedelta(days=7)
    MATTERMOST_MAIN_CHANNEL = os.environ.get(
        "MATTERMOST_MAIN_CHANNEL", "#startup-mobilic"
    )
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_COOKIE_NAME = "at"
    JWT_ACCESS_COOKIE_PATH = "/api"
    JWT_REFRESH_COOKIE_NAME = "rt"
    JWT_REFRESH_COOKIE_PATH = "/api/token"
    JWT_COOKIE_SECURE = True
    JWT_IDENTITY_CLAIM = "identity"
    SESSION_COOKIE_LIFETIME = timedelta(days=365)
    RESET_PASSWORD_TOKEN_EXPIRATION = timedelta(days=1)
    METABASE_COMPANY_DASHBOARD_BASE_URL = os.environ.get(
        "METABASE_COMPANY_DASHBOARD_BASE_URL",
        "https://metabase.mobilic.beta.gouv.fr/dashboard/3?id=",
    )
    USER_READ_TOKEN_EXPIRATION = os.environ.get(
        "USER_READ_TOKEN_EXPIRATION", timedelta(days=7)
    )
    HMAC_SIGNING_KEY = os.environ.get("HMAC_SIGNING_KEY")
    USER_CONTROL_HISTORY_DEPTH = timedelta(
        days=int(os.environ.get("USER_CONTROL_HISTORY_DEPTH", 28))
    )
    MIN_DELAY_BETWEEN_INVITATION_EMAILS = timedelta(
        minutes=os.environ.get(
            "MIN_MINUTES_BETWEEN_INVITATION_EMAILS", 60 * 24
        )
    )
    MIN_MINUTES_BETWEEN_ACTIVATION_EMAILS = timedelta(
        minutes=os.environ.get("MIN_MINUTES_BETWEEN_ACTIVATION_EMAILS", 30)
    )
    ENABLE_NEWSLETTER_SUBSCRIPTION = os.environ.get(
        "ENABLE_NEWSLETTER_SUBSCRIPTION", False
    )

    APISPEC_FORMAT_RESPONSE = lambda x: x

    LIVESTORM_API_TOKEN = os.environ.get("LIVESTORM_API_TOKEN", None)
    DISABLE_EMAIL = os.environ.get("DISABLE_EMAIL", False)
    CONTROL_SIGNING_KEY = os.environ.get("CONTROL_SIGNING_KEY")
    CERTIFICATION_API_KEY = os.environ.get("CERTIFICATION_API_KEY")
    API_KEY_PREFIX = os.environ.get("API_KEY_PREFIX", "mobilic_live_")
    NB_BAD_PASSWORD_TRIES_BEFORE_BLOCKING = 10
    COMPANY_EXCLUDE_ONBOARDING_EMAILS = json.loads(
        os.environ.get("COMPANY_EXCLUDE_ONBOARDING_EMAILS", "[]")
    )
    BATCH_EMAIL_WHITELIST = json.loads(
        os.environ.get("BATCH_EMAIL_WHITELIST", "[]")
    )
    USERS_BLACKLIST = json.loads(os.environ.get("USERS_BLACKLIST", "[]"))
    SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT", "development")
    BREVO_COMPANY_SUBSCRIBE_LIST = os.environ.get(
        "BREVO_COMPANY_SUBSCRIBE_LIST", 19
    )
    CELERY_BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    EXPORT_MAX = int(os.environ.get("EXPORT_MAX", 1000))
    CGU_VERSION = os.environ.get("CGU_VERSION", "v1.0")
    CGU_RELEASE_DATE = (
        datetime.strptime(
            os.environ.get("CGU_RELEASE_DATE"), "%Y-%m-%d"
        ).date()
        if os.environ.get("CGU_RELEASE_DATE")
        else CGU_INITIAL_RELASE_DATE
    )
    START_DATE_FOR_SCHEDULED_INVITATION = (
        datetime.strptime(
            os.environ.get("START_DATE_FOR_SCHEDULED_INVITATION"), "%Y-%m-%d"
        ).date()
        if os.environ.get("START_DATE_FOR_SCHEDULED_INVITATION")
        else datetime(2024, 12, 30)
    )
    ANONYMIZATION_THRESHOLD_YEAR = int(
        os.environ.get("ANONYMIZATION_THRESHOLD_YEAR", 4)
    )
    ANONYMIZATION_USER_BATCH = int(
        os.environ.get("ANONYMIZATION_USER_BATCH", 100)
    )


class DevConfig(Config):
    EMAIL_ACTIVATION_TOKEN_EXPIRATION = timedelta(minutes=10)
    ECHO_DB_QUERIES = os.environ.get("ECHO_DB_QUERIES", False)
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    JWT_COOKIE_SECURE = False
    MIN_DELAY_BETWEEN_INVITATION_EMAILS = timedelta(
        minutes=os.environ.get("MIN_MINUTES_BETWEEN_INVITATION_EMAILS", 2)
    )
    API_KEY_PREFIX = os.environ.get("API_KEY_PREFIX", "mobilic_dev_")
    BREVO_COMPANY_SUBSCRIBE_LIST = os.environ.get(
        "BREVO_COMPANY_SUBSCRIBE_LIST", 22
    )
    CELERY_BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")


class StagingConfig(Config):
    pass


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://mobilic-test:mobilic-test@localhost:5433/mobilic-test",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DISABLE_EMAIL = True
    CONTROL_SIGNING_KEY = "abc"
    CERTIFICATION_API_KEY = "1234"
    BREVO_COMPANY_SUBSCRIBE_LIST = os.environ.get(
        "BREVO_COMPANY_SUBSCRIBE_LIST", 22
    )


class ProdConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=960)  # 16h
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)


class SandboxConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(days=1)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)
