from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.base import BaseModel, RandomNineIntId


class ControllerUser(BaseModel, RandomNineIntId):
    agent_connect_id = db.Column(db.String(255), unique=True, nullable=False)
    agent_connect_info = db.Column(JSONB(none_as_null=True), nullable=True)
    organizational_unit = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".lower().title()

    def query_controls(self, from_date=None):
        from app.models.queries import query_controls

        return query_controls(
            start_time=from_date, end_time=None, controller_user_id=self.id
        ).all()

    def __repr__(self):
        return f"<Controller [{self.id}] : {self.display_name}>"
