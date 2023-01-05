from datetime import datetime

from sqlalchemy import desc

from app.helpers.oauth import OAuth2Token


def get_active_oauth_token_for_user(user_id):
    return (
        OAuth2Token.query.filter(
            OAuth2Token.user_id == user_id,
            OAuth2Token.revoked_at.is_(None),
        )
        .order_by(desc(OAuth2Token.creation_time))
        .all()
    )


def revoke_oauth_token(token):
    token.revoked_at = datetime.now()
    return token
