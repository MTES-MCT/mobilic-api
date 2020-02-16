from app import db
from app.models.event import EventBaseModel


class Comment(EventBaseModel):
    backref_base_name = "comments"

    content = db.Column(db.TEXT, nullable=False)
