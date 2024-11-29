from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.domain.regulations_helper import resolve_variables
from app.models.base import BaseModel
from app.models.utils import enum_column


class RegulationRule(str, Enum):
    DAILY_WORK = "dailyWork"
    DAILY_REST = "dailyRest"
    WEEKLY_WORK = "weeklyWork"
    WEEKLY_REST = "weeklyRest"
    __description__ = """
Enumération des valeurs suivantes.
- "dailyWork" : durée du travail quotidien
- "dailyRest" : pause et repos quotidiens
- "weeklyWork" : durée du travail hebdomadaire
- "weeklyRest" : repos hebdomadaire
"""


class UnitType(str, Enum):
    DAY = "day"
    WEEK = "week"
    __description__ = """
Enumération des valeurs suivantes.
- "day" : règle journalière
- "week" : règle hebdomadaire
"""


class RegulationCheckType(str, Enum):
    MINIMUM_DAILY_REST = "minimumDailyRest"
    MAXIMUM_WORK_DAY_TIME = "maximumWorkDayTime"
    MINIMUM_WORK_DAY_BREAK = "minimumWorkDayBreak"
    MAXIMUM_UNINTERRUPTED_WORK_TIME = "maximumUninterruptedWorkTime"
    MAXIMUM_WORKED_DAY_IN_WEEK = "maximumWorkedDaysInWeek"
    NO_LIC = "noLic"
    MAXIMUM_WORK_IN_CALENDAR_WEEK = "maximumWorkInCalendarWeek"
    __description__ = """
Enumération des valeurs suivantes.
- "minimumDailyRest" : non-respect(s) du repos quotidien
- "maximumWorkDayTime" : dépassement(s) de la durée maximale du travail quotidien
- "minimumWorkDayBreak" : non-respect(s) du temps de pause
- "maximumUninterruptedWorkTime" : dépassement(s) de la durée maximale du travail ininterrompu
- "maximumWorkedDaysInWeek" : non-respect(s) du repos hebdomadaire
- "noLic" : pas de LIC présenté lors du contrôle
- "maximumWorkInCalendarWeek": Dépassement(s) de la durée maximale de travail hebdomadaire sur une semaine civile isolée
"""


class RegulationCheck(BaseModel):
    backref_base_name = "regulation_checks"

    type = enum_column(RegulationCheckType, nullable=False)
    label = db.Column(db.String(255), nullable=False)
    date_application_start = db.Column(db.Date, nullable=False)
    date_application_end = db.Column(db.Date, nullable=True)
    regulation_rule = enum_column(RegulationRule, nullable=True)
    variables = db.Column(JSONB(none_as_null=True), nullable=True)
    unit = enum_column(UnitType, nullable=False)

    def resolve_variables(self, business=None):
        if not business:
            from app.domain.regulations import get_default_business

            business = getattr(self, "business", None)
            if business is None:
                business = get_default_business()
        return resolve_variables(self.variables, business)

    def __repr__(self):
        return f"<RegulationCheck [{self.id}] : {self.type}>"
