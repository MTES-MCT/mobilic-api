from enum import Enum

from app import db
from app.models.base import BaseModel
from app.models.utils import enum_column


class Scenario(str, Enum):
    SCENARIO_A = "Certificate banner"
    SCENARIO_B = "Certificate badge"


class Action(str, Enum):
    LOAD = "Load"
    SUCCESS = "Success"
    CLOSE = "Close"


class ScenarioTesting(BaseModel):
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="scenario_testing_results")
    scenario = enum_column(Scenario, nullable=False)
    action = enum_column(Action, nullable=False)
