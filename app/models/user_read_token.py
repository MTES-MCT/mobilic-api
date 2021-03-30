import secrets
import graphene
from datetime import datetime, date, timezone
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func, Date

from app import db, app
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.graphene_types import TimeStamp, BaseSQLAlchemyObjectType
from app.models.base import BaseModel
from app.helpers.errors import InvalidTokenError, TokenExpiredError


TOKEN_BYTES_LENGTH = 32


class UserReadToken(BaseModel):
    token = db.Column(
        db.Text,
        nullable=False,
        unique=True,
        default=lambda: secrets.token_urlsafe(TOKEN_BYTES_LENGTH),
    )

    valid_until = db.Column(DateTimeStoredAsUTC, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="read_tokens")

    @property
    def history_start_day(self):
        return self.creation_day - app.config["USER_CONTROL_HISTORY_DEPTH"]

    @hybrid_property
    def creation_day(self):
        utc_creation_time = self.creation_time.astimezone(timezone.utc)
        return date(
            utc_creation_time.year,
            utc_creation_time.month,
            utc_creation_time.day,
        )

    @creation_day.expression
    def creation_day(cls):
        return func.cast(cls.creation_time, Date)

    @staticmethod
    def get_or_create(user):
        user_valid_tokens = UserReadToken.query.filter(
            UserReadToken.user_id == user.id,
            UserReadToken.valid_until >= datetime.now(),
            UserReadToken.creation_day == func.current_date(),
        ).all()
        valid_until = datetime.now() + app.config["USER_READ_TOKEN_EXPIRATION"]
        if user_valid_tokens:
            token = user_valid_tokens[0]
            token.valid_until = valid_until
        else:
            token = UserReadToken(user=user, valid_until=valid_until)
        db.session.add(token)
        db.session.commit()
        return token

    @staticmethod
    def get_token(token):
        token = UserReadToken.query.filter(
            UserReadToken.token == token
        ).one_or_none()
        if not token:
            raise InvalidTokenError("Invalid token")
        if token.valid_until < datetime.now():
            raise TokenExpiredError("Expired token")
        return token


class UserReadTokenOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = UserReadToken
        only_fields = ("creation_time", "creation_day", "valid_until")

    creation_time = graphene.Field(TimeStamp, required=True)
    creation_day = graphene.Field(graphene.Date, required=True)
    valid_until = graphene.Field(TimeStamp, required=True)

    history_start_day = graphene.Field(graphene.Date, required=True)
