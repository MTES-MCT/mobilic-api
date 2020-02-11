class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MINIMUM_ACTIVITY_DURATION = 5
    ACCESS_TOKEN_EXPIRATION = 100
    JWT_SECRET_KEY = "my-little-secret"
    DISABLE_AUTH_FOR_TESTING = True


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/mobilic-test"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
