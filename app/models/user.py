from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import synonym
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4

from app.models.base import BaseModel
from app import db


class User(BaseModel):
    email = db.Column(db.String(255), unique=True, nullable=True, default=None)
    _password = db.Column("password", db.String(255), default=None)
    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="users", lazy="selectin")
    company_name_to_resolve = db.Column(db.String(255))
    refresh_token_nonce = db.Column(db.String(255), default=None)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    is_company_admin = db.Column(db.Boolean, default=False, nullable=False)
    admin = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, plain_text):
        password_hash = generate_password_hash(plain_text.encode("utf8"))
        self._password = password_hash

    def check_password(self, plain_text):
        return check_password_hash(self.password, plain_text.encode("utf-8"))

    password = synonym("_password", descriptor=password)

    @staticmethod
    def _generate_id():
        while True:
            id_ = int(str(uuid4().int)[:9])
            if User.query.get(id_) is None:
                return id_

    @property
    def acknowledged_activities(self):
        return sorted(
            [
                activity
                for activity in self.activities
                if activity.is_acknowledged
            ],
            key=lambda a: a.user_time,
        )

    @property
    def acknowledged_deduplicated_activities(self):
        return [a for a in self.acknowledged_activities if not a.is_duplicate]

    def latest_acknowledged_activity_at(self, date_time):
        acknowledged_activities = [
            a for a in self.acknowledged_activities if a.user_time <= date_time
        ]
        if not acknowledged_activities:
            return None
        return acknowledged_activities[-1]

    @property
    def current_activity(self):
        acknowledged_activities = self.acknowledged_activities
        if not acknowledged_activities:
            return None
        return acknowledged_activities[-1]

    @property
    def enrollable_coworkers(self):
        now = datetime.now()
        return [
            u
            for u in self.company.users
            if not u.is_company_admin and u.mission_at(now) is None
        ]

    @property
    def bookable_vehicles(self):
        # TODO : add logic that hides vehicles currently booked by other people
        return [v for v in self.company.vehicles if not v.is_terminated]

    def missions(self, include_dismisses_and_revisions=False):
        sorted_missions = []
        missions = set()
        activities = (
            self.acknowledged_activities
            if not include_dismisses_and_revisions
            else self.activities
        )
        for a in activities:
            if a.mission not in missions:
                sorted_missions.append(a.mission)
                missions.add(a.mission)
        return sorted_missions

    def mission_at(self, date_time):
        from app.models.activity import ActivityType

        latest_activity_at_time = self.latest_acknowledged_activity_at(
            date_time
        )
        if (
            not latest_activity_at_time
            or latest_activity_at_time.type == ActivityType.REST
        ):
            return None
        return latest_activity_at_time.mission

    def revoke_refresh_token(self):
        self.refresh_token_nonce = None

    def generate_refresh_token_nonce(self):
        self.refresh_token_nonce = uuid4().hex
        return self.refresh_token_nonce

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User [{self.id}] : {self.display_name}>"


@dataclass
class TeamEnrollmentPeriod:
    submitter: User
    start_time: datetime
    end_time: datetime = None
