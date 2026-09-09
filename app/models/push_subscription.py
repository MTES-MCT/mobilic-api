from app import db
from app.models.base import BaseModel


class PushSubscription(BaseModel):
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="push_subscriptions")
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh_key = db.Column(db.Text, nullable=False)
    auth_key = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
