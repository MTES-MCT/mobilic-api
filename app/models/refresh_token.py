from uuid import uuid4
from datetime import datetime

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel

MAX_TOKENS_PER_USER = 5


class RefreshToken(BaseModel):
    token = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
        default=lambda: str(uuid4()),
    )

    consumed_at = db.Column(DateTimeStoredAsUTC, nullable=True)
    deleted_at = db.Column(DateTimeStoredAsUTC, nullable=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="refresh_tokens")

    @property
    def is_active(self):
        return self.consumed_at is None and self.deleted_at is None

    @staticmethod
    def create_refresh_token(user):
        now = datetime.now()
        current_refresh_tokens = sorted(
            [r for r in user.refresh_tokens if r.is_active],
            key=lambda rt: rt.creation_time,
        )
        oldest_token_index = 0
        while (
            oldest_token_index
            <= len(current_refresh_tokens) - MAX_TOKENS_PER_USER
        ):
            current_refresh_tokens[oldest_token_index].deleted_at = now
            oldest_token_index += 1
        refresh_token = RefreshToken(user=user)
        db.session.add(refresh_token)
        db.session.flush()
        return refresh_token.token

    @staticmethod
    def get_token(token, user_id):
        return RefreshToken.query.filter(
            RefreshToken.token == token,
            RefreshToken.user_id == user_id,
            RefreshToken.consumed_at.is_(None),
            RefreshToken.deleted_at.is_(None),
        ).one_or_none()
