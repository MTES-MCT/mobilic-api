from datetime import date
from sqlalchemy.dialects.postgresql import JSONB

from app.helpers.employment import WithEmploymentHistory
from app.models.base import BaseModel
from app import db


class Company(BaseModel, WithEmploymentHistory):
    usual_name = db.Column(db.String(255), nullable=False)

    siren = db.Column(db.Integer, unique=False, nullable=True)

    short_sirets = db.Column(db.ARRAY(db.Integer), nullable=True)

    siren_api_info = db.Column(JSONB(none_as_null=True), nullable=True)

    # Parameters of work day logging
    allow_team_mode = db.Column(db.Boolean, nullable=False, default=True)
    require_kilometer_data = db.Column(
        db.Boolean, nullable=False, default=True
    )
    require_expenditures = db.Column(db.Boolean, nullable=False, default=True)
    require_support_activity = db.Column(
        db.Boolean, nullable=False, default=False
    )
    require_mission_name = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.Constraint(name="only_one_company_per_siret"),)

    @property
    def name(self):
        return self.usual_name

    def __repr__(self):
        return f"<Company [{self.id}] : {self.name}>"

    @property
    def users(self):
        today = date.today()
        return [e.user for e in self.active_employments_at(today)]

    def users_between(self, start, end):
        return [e.user for e in self.active_employments_between(start, end)]

    def query_current_users(self):
        from app.models import User

        today = date.today()

        user_ids = [e.user_id for e in self.active_employments_at(today)]
        return User.query.filter(User.id.in_(user_ids))
