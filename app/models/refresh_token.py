from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_

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

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="refresh_tokens")

    # Rotation bookkeeping : a consumed token is kept (until purge) so that
    # a client replaying it within the reuse grace period can recover the
    # successor chain instead of being logged out.
    consumed_at = db.Column(DateTimeStoredAsUTC, nullable=True)
    replaced_by_token = db.Column(db.String(128), nullable=True)

    @staticmethod
    def create_refresh_token(user):
        live_refresh_tokens = sorted(
            [rt for rt in user.refresh_tokens if rt.consumed_at is None],
            key=lambda rt: rt.creation_time,
        )
        oldest_token_index = 0
        while (
            oldest_token_index
            <= len(live_refresh_tokens) - MAX_TOKENS_PER_USER
        ):
            db.session.delete(live_refresh_tokens[oldest_token_index])
            oldest_token_index += 1
        refresh_token = RefreshToken(user=user)
        db.session.add(refresh_token)
        db.session.flush()
        return refresh_token.token

    @staticmethod
    def get_token(token, user_id):
        return RefreshToken.query.filter(
            RefreshToken.token == token, RefreshToken.user_id == user_id
        ).one_or_none()

    @staticmethod
    def consume(token, user_id):
        """Atomically mark the token as consumed.

        The conditional UPDATE guarantees that concurrent refresh requests
        presenting the same token cannot both win the rotation.
        Returns the consumed token or None if it was already consumed
        or does not exist.
        """
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        row = db.session.execute(
            RefreshToken.__table__.update()
            .where(
                and_(
                    RefreshToken.__table__.c.token == token,
                    RefreshToken.__table__.c.user_id == user_id,
                    RefreshToken.__table__.c.consumed_at.is_(None),
                )
            )
            .values(consumed_at=now)
            .returning(RefreshToken.__table__.c.id)
        ).fetchone()
        if row is None:
            return None
        consumed = RefreshToken.query.get(row[0])
        # Sync the identity map with the Core UPDATE so callers iterating
        # user.refresh_tokens see this row as consumed (cap eviction).
        consumed.consumed_at = now
        return consumed
