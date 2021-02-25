import secrets
from datetime import datetime

from app import db, app
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

    valid_until = db.Column(db.DateTime, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="read_tokens")

    @staticmethod
    def get_or_create(user):
        user_valid_tokens = UserReadToken.query.filter(
            UserReadToken.user_id == user.id,
            UserReadToken.valid_until >= datetime.now(),
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
