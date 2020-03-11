from enum import Enum
from app.models.event import EventBaseModel
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
