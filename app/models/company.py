from datetime import date
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel
from app import db


class Company(BaseModel):
    usual_name = db.Column(db.String(255), nullable=False)

    siren = db.Column(db.Integer, unique=True, nullable=True)

    sirets = db.Column(db.ARRAY(db.String(14)), nullable=True)

    siren_api_info = db.Column(JSONB(none_as_null=True), nullable=True)

    @property
    def name(self):
        return self.usual_name

    def __repr__(self):
        return f"<Company [{self.id}] : {self.name}>"

    @property
    def users(self):
        return [e.user for e in self._active_employments()]

    def _active_employments(self):
        return [
            e
            for e in self.employments
            if e.is_acknowledged
            and e.start_date
            <= date.today()
            <= (e.end_date or date(2100, 1, 1))
        ]

    def query_users(self):
        from app.models import User

        user_ids = [e.user_id for e in self._active_employments()]
        return User.query.filter(User.id.in_(user_ids))
