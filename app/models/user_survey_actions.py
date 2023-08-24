from enum import Enum

import graphene

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.base import BaseModel
from app.models.utils import enum_column


class SurveyAction(str, Enum):
    DISPLAY = "DISPLAY"
    CLOSE = "CLOSE"
    SUBMIT = "SUBMIT"


class UserSurveyActions(BaseModel):
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="survey_actions")
    survey_id = db.Column(db.String(255), nullable=False, index=True)
    action = enum_column(SurveyAction, nullable=False)


class UserSurveyActionsOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = UserSurveyActions
        only_fields = ("creation_time", "survey_id", "action")

    creation_time = TimeStamp(description="Date de l'action.")
