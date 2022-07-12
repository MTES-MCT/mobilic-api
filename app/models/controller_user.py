from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.base import BaseModel, RandomNineIntId


class ControllerUser(BaseModel, RandomNineIntId):
    agent_connect_id = db.Column(db.String(255), unique=True, nullable=False)
    agent_connect_info = db.Column(JSONB(none_as_null=True), nullable=True)
    organizational_unit = db.Column(
        db.String(255), unique=True, nullable=False
    )
    email = db.Column(db.String(255), nullable=True, default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".lower().title()

    def __repr__(self):
        return f"<Controller [{self.id}] : {self.display_name}>"
