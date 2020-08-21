from uuid import uuid4

from app import db
from app.models.base import BaseModel

MAX_TOKENS_PER_USER = 5


class RefreshToken(BaseModel):
    token = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
        default=lambda: uuid4().hex,
    )

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="refresh_tokens")

    @staticmethod
    def create_refresh_token(user):
        current_refresh_tokens = sorted(
            user.refresh_tokens, key=lambda rt: rt.creation_time
        )
        oldest_token_index = 0
        while (
            oldest_token_index
            <= len(current_refresh_tokens) - MAX_TOKENS_PER_USER
        ):
            db.session.delete(current_refresh_tokens[oldest_token_index])
            oldest_token_index += 1
        refresh_token = RefreshToken(user=user)
        db.session.add(refresh_token)
        return refresh_token.token

    @staticmethod
    def get_token(token, user_id):
        return RefreshToken.query.filter(
            RefreshToken.token == token, RefreshToken.user_id == user_id
        ).one_or_none()
