import graphene
from flask import request

from app import db
from app.controllers.utils import Void
from app.helpers.authentication import (
    current_user,
    AuthenticatedMutation,
)
from app.helpers.authorization import (
    with_authorization_policy,
    active,
)
from app.models.push_subscription import PushSubscription


class SavePushSubscription(AuthenticatedMutation):
    class Arguments:
        endpoint = graphene.String(required=True)
        p256dh = graphene.String(required=True)
        auth = graphene.String(required=True)

    Output = Void

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, endpoint, p256dh, auth):
        existing = PushSubscription.query.filter_by(
            endpoint=endpoint
        ).one_or_none()

        if existing:
            if existing.user_id == current_user.id:
                existing.p256dh_key = p256dh
                existing.auth_key = auth
                existing.user_agent = request.headers.get(
                    "User-Agent"
                )
                db.session.commit()
                return Void(success=True)
            else:
                db.session.delete(existing)
                db.session.flush()

        subscription = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
            user_agent=request.headers.get("User-Agent"),
        )
        db.session.add(subscription)
        db.session.commit()
        return Void(success=True)


class DeletePushSubscription(AuthenticatedMutation):
    class Arguments:
        endpoint = graphene.String(required=True)

    Output = Void

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, endpoint):
        PushSubscription.query.filter_by(
            endpoint=endpoint, user_id=current_user.id
        ).delete()
        db.session.commit()
        return Void(success=True)
