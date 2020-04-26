from enum import Enum

from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import UserEventBaseModel, Dismissable, DismissType
from app.models.utils import enum_column


class ExpenditureType(str, Enum):
    DAY_MEAL = "day_meal"
    NIGHT_MEAL = "night_meal"
    SLEEP_OVER = "sleep_over"
    SNACK = "snack"


class Expenditure(UserEventBaseModel, Dismissable):
    backref_base_name = "expenditures"

    type = enum_column(ExpenditureType, nullable=False)


class ExpenditureOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureType)()
    dismiss_type = graphene_enum_type(DismissType)(required=False)
