from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MINIMUM_ACTIVITY_DURATION = timedelta(seconds=100)
    ACCESS_TOKEN_EXPIRATION = timedelta(seconds=100)
    JWT_SECRET_KEY = "my-little-secret"
    DISABLE_AUTH_FOR_TESTING = False


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic-test"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
