from enum import Enum

from app import db
from app.models.base import BaseModel
from app.models.utils import enum_column


class CertificateInfoScenario(str, Enum):
    SCENARIO_A = "Scenario A"
    SCENARIO_B = "Scenario B"


class CertificateInfoAction(str, Enum):
    LOAD = "Load"
    SUCCESS = "Success"
    CLOSE = "Close"


class CertificateInfoResult(BaseModel):
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="certificate_info_results")
    scenario = enum_column(CertificateInfoScenario, nullable=False)
    action = enum_column(CertificateInfoAction, nullable=False)
