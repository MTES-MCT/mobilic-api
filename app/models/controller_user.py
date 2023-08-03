import re

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.base import BaseModel, RandomNineIntId


class ControllerUser(BaseModel, RandomNineIntId):
    agent_connect_id = db.Column(db.String(255), unique=True, nullable=False)
    agent_connect_info = db.Column(JSONB(none_as_null=True), nullable=True)
    organizational_unit = db.Column(db.String(255), nullable=False)
    greco_id = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True, default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".lower().title()

    def __repr__(self):
        return f"<Controller [{self.id}] : {self.display_name}>"

    @property
    def pretty_organizational_unit(self):
        organizational_units = self.organizational_unit.split("/")
        if self._is_ctt():
            return organizational_units[0]
        elif self._is_it() and len(organizational_units) > 1:
            return organizational_units[1] + " " + organizational_units[0]
        else:
            return self.organizational_unit

    def _is_ctt(self):
        return re.search(
            "DEAL|DRIEAT|DRIEA|DREAL", self.organizational_unit, re.IGNORECASE
        )

    def _is_it(self):
        return re.search(
            "DREETS|DRIETS|DDETS", self.organizational_unit, re.IGNORECASE
        )
