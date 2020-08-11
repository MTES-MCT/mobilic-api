from datetime import date

from sqlalchemy.orm import synonym
from werkzeug.security import generate_password_hash, check_password_hash
from cached_property import cached_property
from uuid import uuid4
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel
from app import db


class User(BaseModel):
    email = db.Column(db.String(255), unique=True, nullable=True, default=None)
    _password = db.Column("password", db.String(255), default=None)
    refresh_token_nonce = db.Column(db.String(255), default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    admin = db.Column(db.Boolean, default=False, nullable=False)
    ssn = db.Column(db.String(13), nullable=True)

    france_connect_id = db.Column(db.String(255), unique=True, nullable=True)
    france_connect_info = db.Column(JSONB(none_as_null=True), nullable=True)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, plain_text):
        if plain_text:
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
            key=lambda a: a.start_time,
        )

    def latest_acknowledged_activity_at(self, date_time):
        acknowledged_activities = [
            a
            for a in self.acknowledged_activities
            if a.start_time <= date_time
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

    def missions(self, include_dismisses_and_revisions=False):
        sorted_missions = []
        missions = set()
        activities = sorted(
            self.acknowledged_activities
            if not include_dismisses_and_revisions
            else self.activities,
            key=lambda a: a.start_time,
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

    @property
    def primary_company(self):
        current_primary_employment = self.primary_employment_at(date.today())
        return (
            current_primary_employment.company
            if current_primary_employment
            else None
        )

    def employments_at(self, date_, with_pending_ones=False):
        employments = sorted(
            [
                e
                for e in self.employments
                if e.is_not_rejected
                and e.start_date <= date_ <= (e.end_date or date(2100, 1, 1))
            ],
            key=lambda e: not e.is_primary,
        )
        if not with_pending_ones:
            return [e for e in employments if e.is_acknowledged]
        return employments

    def primary_employment_at(self, date_):
        employments = self.employments_at(date_)
        if employments and employments[0].is_primary:
            return employments[0]
        else:
            return None

    @cached_property
    def current_company_ids_with_admin_rights(self):
        return [
            e.company_id
            for e in self.employments_at(date.today())
            if e.has_admin_rights
        ]
