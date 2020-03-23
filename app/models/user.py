from collections import defaultdict
from sqlalchemy.orm import synonym
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4

from app.models.base import BaseModel
from app import db


class User(BaseModel):
    email = db.Column(db.String(255), unique=True, nullable=True, default=None)
    _password = db.Column("password", db.String(255), default=None)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), index=True)
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
            key=lambda a: a.start_time,
        )

    @property
    def acknowledged_deduplicated_activities(self):
        return [a for a in self.acknowledged_activities if not a.is_duplicate]

    @property
    def acknowledged_expenditures(self):
        return sorted(
            [
                expenditure
                for expenditure in self.expenditures
                if expenditure.is_acknowledged
            ],
            key=lambda e: e.event_time,
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
    def current_acknowledged_activity(self):
        acknowledged_activities = self.acknowledged_activities
        if not acknowledged_activities:
            return None
        return acknowledged_activities[-1]

    @property
    def acknowledged_submitted_team_enrollments(self):
        return sorted(
            [
                enrollment
                for enrollment in self.submitted_team_enrollments
                if enrollment.is_acknowledged
            ],
            key=lambda e: e.action_time,
        )

    @property
    def acknowledged_team_enrollments(self):
        return sorted(
            [
                enrollment
                for enrollment in self.team_enrollments
                if enrollment.is_acknowledged
            ],
            key=lambda e: e.action_time,
        )

    def acknowledged_team_at(self, date_time):
        from app.models.team_enrollment import TeamEnrollmentType

        relevant_team_enrollments = [
            e
            for e in self.acknowledged_submitted_team_enrollments
            if date_time >= e.action_time
        ]
        relevant_team_enrollments_by_user = defaultdict(list)
        for rte in relevant_team_enrollments:
            relevant_team_enrollments_by_user[rte.user].append(rte)
        return [
            u
            for u in relevant_team_enrollments_by_user
            if relevant_team_enrollments_by_user[u][-1].type
            == TeamEnrollmentType.ENROLL
        ]

    @property
    def enrollable_coworkers(self):
        from app.models.team_enrollment import TeamEnrollmentType

        enrollable_coworkers = []
        for coworker in self.company.users:
            if coworker != self and not coworker.is_company_admin:
                team_enrollments = coworker.acknowledged_team_enrollments
                latest_team_enrollment = (
                    team_enrollments[-1] if team_enrollments else None
                )
                if (
                    not latest_team_enrollment
                    or latest_team_enrollment.type == TeamEnrollmentType.REMOVE
                    or latest_team_enrollment.submitter == self
                ):
                    enrollable_coworkers.append(coworker)
        return enrollable_coworkers

    def revoke_refresh_token(self):
        self.refresh_token_nonce = None

    def generate_refresh_token_nonce(self):
        self.refresh_token_nonce = uuid4().hex
        return self.refresh_token_nonce

    def to_dict(self):
        return dict(
            id=self.id,
            email=self.email,
            company=self.company.to_dict(),
            first_name=self.first_name,
            last_name=self.last_name,
        )

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User [{self.id}] : {self.display_name}>"
