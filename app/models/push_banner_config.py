from app import db
from app.helpers.db import DateTimeStoredAsUTC


class PushBannerConfig(db.Model):
    __tablename__ = "push_banner_config"

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=False
    )
    banner_text = db.Column(db.Text, nullable=False)
    updated_at = db.Column(DateTimeStoredAsUTC, nullable=False)
    updated_by_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )
    updated_by = db.relationship("User")

    SINGLETON_ID = 1

    @classmethod
    def get_current(cls):
        return cls.query.get(cls.SINGLETON_ID)
