from sqlalchemy.orm import synonym
from werkzeug.security import generate_password_hash
from uuid import uuid4

from app.models.base import BaseModel
from app import db


class User(BaseModel):
    email = db.Column(db.String(255), unique=True)
    _password = db.Column("password", db.String(255))
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), index=True)
    company = db.relationship("Company", backref="users")
    token = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, plain_text):
        password_hash = generate_password_hash(plain_text.encode("utf8"))
        self._password = password_hash

    password = synonym("_password", descriptor=password)

    @staticmethod
    def _generate_id():
        while True:
            id_ = int(str(uuid4().int)[:9])
            if User.query.get(id_) is None:
                return id_

    @property
    def acknowledged_activities(self):
        return [
            activity
            for activity in self.activities
            if activity.is_acknowledged
        ]

    @property
    def current_acknowledged_activity(self):
        acknowledged_activities = self.acknowledged_activities
        if not acknowledged_activities:
            return None
        return max(acknowledged_activities, key=lambda act: act.event_time)
