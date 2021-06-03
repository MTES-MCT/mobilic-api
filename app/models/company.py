from datetime import date
from sqlalchemy.dialects.postgresql import JSONB

from app.helpers.time import VERY_FAR_AHEAD, VERY_LONG_AGO
from app.models.base import BaseModel
from app import db


class Company(BaseModel):
    usual_name = db.Column(db.String(255), nullable=False)

    siren = db.Column(db.Integer, unique=True, nullable=True)

    sirets = db.Column(db.ARRAY(db.String(14)), nullable=True)

    siren_api_info = db.Column(JSONB(none_as_null=True), nullable=True)

    allow_team_mode = db.Column(db.Boolean, nullable=False, default=True)
    require_kilometer_data = db.Column(
        db.Boolean, nullable=False, default=True
    )

    @property
    def name(self):
        return self.usual_name

    def __repr__(self):
        return f"<Company [{self.id}] : {self.name}>"

    @property
    def users(self):
        today = date.today()
        return [e.user for e in self._active_employments_between(today, today)]

    def users_between(self, start, end):
        return [e.user for e in self._active_employments_between(start, end)]

    def _active_employments_between(self, start=None, end=None):
        end_ = end or date.today()
        start_ = start or VERY_LONG_AGO.date()
        return [
            e
            for e in self.employments
            if e.is_acknowledged
            and e.start_date <= end_
            and (e.end_date or VERY_FAR_AHEAD.date()) >= start_
        ]

    def query_current_users(self):
        from app.models import User

        today = date.today()

        user_ids = [
            e.user_id for e in self._active_employments_between(today, today)
        ]
        return User.query.filter(User.id.in_(user_ids))
