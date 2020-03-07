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

    @property
    def current_acknowledged_activity(self):
        acknowledged_activities = self.acknowledged_activities
        if not acknowledged_activities:
            return None
        return acknowledged_activities[-1]

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
