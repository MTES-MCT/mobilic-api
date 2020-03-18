from enum import Enum
import graphene

from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import EventBaseModel, DismissType
from app.models.utils import enum_column


class ExpenditureType(str, Enum):
    DAY_MEAL = "day_meal"
    NIGHT_MEAL = "night_meal"
    SLEEP_OVER = "sleep_over"
    SNACK = "snack"


class Expenditure(EventBaseModel):
    backref_base_name = "expenditures"

    type = enum_column(ExpenditureType, nullable=False)

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type,)


class ExpenditureOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureType)()
    team = graphene.List(graphene.Int)
    dismiss_type = graphene_enum_type(DismissType)(required=False)
