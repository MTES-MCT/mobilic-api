from enum import Enum
from sqlalchemy.orm import backref

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import UserEventBaseModel, Dismissable
from app.models.utils import enum_column


class ExpenditureType(str, Enum):
    DAY_MEAL = "day_meal"
    NIGHT_MEAL = "night_meal"
    SLEEP_OVER = "sleep_over"
    SNACK = "snack"


class Expenditure(UserEventBaseModel, Dismissable):
    backref_base_name = "expenditures"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("expenditures"))

    type = enum_column(ExpenditureType, nullable=False)

    def __repr__(self):
        return f"<Expenditure [{self.id}] : {self.type.value}>"


class ExpenditureOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureType)()
