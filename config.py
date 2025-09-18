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
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
    S3_REGION = os.environ.get("S3_REGION")
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

    # FranceConnect v2
    FC_V2_URL = os.environ.get(
        "FC_V2_URL", "https://oidc.franceconnect.gouv.fr"
    )
    FC_V2_CLIENT_ID = os.environ.get("FC_V2_CLIENT_ID")
    FC_V2_CLIENT_SECRET = os.environ.get("FC_V2_CLIENT_SECRET")
    FC_TIMEOUT = int(os.environ.get("FC_TIMEOUT", "10"))
    # FranceConnect v2 development redirect URI override (for local testing)
    FC_V2_REDIRECT_URI_OVERRIDE = os.environ.get("FC_V2_REDIRECT_URI_OVERRIDE")

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
    MATTERMOST_ALERT_CHANNEL = os.environ.get(
        "MATTERMOST_ALERT_CHANNEL", "#startup-mobilic-alerts"
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
        os.environ.get("ANONYMIZATION_THRESHOLD_YEAR", 3)
    )
    ANONYMIZATION_THRESHOLD_MONTH = int(
        os.environ.get("ANONYMIZATION_THRESHOLD_MONTH", 0)
    )
    EMAIL_NO_INVITATIONS_DELAY_DAYS = int(
        os.environ.get("EMAIL_NO_INVITATIONS_DELAY_DAYS", 2)
    )
    EMAIL_NO_INVITATIONS_REMINDER_DELAY_DAYS = int(
        os.environ.get("EMAIL_NO_INVITATIONS_REMINDER_DELAY_DAYS", 7)
    )

    # Trusted domains for redirect URL validation
    TRUSTED_REDIRECT_DOMAINS = {
        "mobilic.beta.gouv.fr",
        "mobilic.preprod.beta.gouv.fr",
    }

    # Trusted FranceConnect domains for authorization/logout URLs
    TRUSTED_FRANCECONNECT_DOMAINS = {
        "fcp-low.sbx.dev-franceconnect.fr",  # sandbox
        "fcp.integ01.dev-franceconnect.fr",
        "app.franceconnect.gouv.fr",
        "oidc.franceconnect.gouv.fr",
    }


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

    TRUSTED_REDIRECT_DOMAINS = {
        "localhost",
        "127.0.0.1",
        "testdev.localhost",
        "mobilic.preprod.beta.gouv.fr",
    }


class StagingConfig(Config):
    TRUSTED_REDIRECT_DOMAINS = {
        "mobilic.preprod.beta.gouv.fr",
        # Note: Add PR review app domains as needed for future PRs
    }


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

    TRUSTED_REDIRECT_DOMAINS = {
        "localhost",
        "127.0.0.1",
        "testdev.localhost",
    }


class ProdConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(minutes=960)  # 16h
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)

    TRUSTED_REDIRECT_DOMAINS = {
        "mobilic.beta.gouv.fr",
    }


class SandboxConfig(Config):
    ACCESS_TOKEN_EXPIRATION = timedelta(days=1)
    MINIMUM_ACTIVITY_DURATION = timedelta(minutes=0)

    TRUSTED_REDIRECT_DOMAINS = {
        "mobilic.preprod.beta.gouv.fr",
    }
