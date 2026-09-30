from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel

MAX_TOKENS_PER_USER = 5


class ControllerRefreshToken(BaseModel):
    token = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
        default=lambda: str(uuid4()),
    )

    controller_user_id = db.Column(
        db.Integer,
        db.ForeignKey("controller_user.id"),
        nullable=False,
        index=True,
    )
    controller_user = db.relationship(
        "ControllerUser", backref="refresh_tokens"
    )

    # Rotation bookkeeping, see RefreshToken.
    consumed_at = db.Column(DateTimeStoredAsUTC, nullable=True)
    replaced_by_token = db.Column(db.String(128), nullable=True)

    @staticmethod
    def create_controller_refresh_token(controller_user):
        live_refresh_tokens = sorted(
            [
                rt
                for rt in controller_user.refresh_tokens
                if rt.consumed_at is None
            ],
            key=lambda rt: rt.creation_time,
        )
        oldest_token_index = 0
        while (
            oldest_token_index
            <= len(live_refresh_tokens) - MAX_TOKENS_PER_USER
        ):
            db.session.delete(live_refresh_tokens[oldest_token_index])
            oldest_token_index += 1
        refresh_token = ControllerRefreshToken(controller_user=controller_user)
        db.session.add(refresh_token)
        db.session.flush()
        return refresh_token.token

    @staticmethod
    def get_token(token, controller_user_id):
        return ControllerRefreshToken.query.filter(
            ControllerRefreshToken.token == token,
            ControllerRefreshToken.controller_user_id == controller_user_id,
        ).one_or_none()

    @staticmethod
    def consume(token, controller_user_id):
        """Atomically mark the token as consumed, see RefreshToken.consume."""
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        row = db.session.execute(
            ControllerRefreshToken.__table__.update()
            .where(
                and_(
                    ControllerRefreshToken.__table__.c.token == token,
                    ControllerRefreshToken.__table__.c.controller_user_id
                    == controller_user_id,
                    ControllerRefreshToken.__table__.c.consumed_at.is_(None),
                )
            )
            .values(consumed_at=now)
            .returning(ControllerRefreshToken.__table__.c.id)
        ).fetchone()
        if row is None:
            return None
        consumed = ControllerRefreshToken.query.get(row[0])
        consumed.consumed_at = now
        return consumed
