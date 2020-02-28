from enum import Enum
from app import db
from app.models.event import EventBaseModel
from app.models.utils import enum_column


class ExpenditureTypes(str, Enum):
    DAY_MEAL = "day_meal"
    NIGHT_MEAL = "night_meal"
    SLEEP_OVER = "sleep_over"
    SNACK = "snack"


class Expenditure(EventBaseModel):
    backref_base_name = "expenditures"

    type = enum_column(ExpenditureTypes, nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_acknowledged(self):
        return super().is_acknowledged and self.cancelled_at is None

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type,)
