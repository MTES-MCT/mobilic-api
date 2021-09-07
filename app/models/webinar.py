from datetime import datetime, timedelta

from app import db
from app.helpers.time import to_timestamp
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel


class Webinar(BaseModel):
    time = db.Column(DateTimeStoredAsUTC, nullable=False)
    title = db.Column(db.TEXT, nullable=False)
    link = db.Column(db.TEXT, nullable=False)

    def is_past(self):
        return self.time < datetime.now() + timedelta(hours=6)

    def output(self):
        return {
            "title": self.title,
            "link": self.link,
            "time": to_timestamp(self.time),
        }
