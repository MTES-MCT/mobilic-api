from uuid import uuid4

from app import db
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

    @staticmethod
    def create_controller_refresh_token(controller_user):
        current_refresh_tokens = sorted(
            controller_user.refresh_tokens, key=lambda rt: rt.creation_time
        )
        oldest_token_index = 0
        while (
            oldest_token_index
            <= len(current_refresh_tokens) - MAX_TOKENS_PER_USER
        ):
            db.session.delete(current_refresh_tokens[oldest_token_index])
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
