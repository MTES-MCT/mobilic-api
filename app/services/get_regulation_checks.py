import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from app.models.regulation_check import RegulationCheckType, RegulationRule


@dataclass
class RegulationCheckData:
    type: RegulationCheckType
    label: str
    description: str
    regulation_rule: RegulationRule
    variables: str
    date_application_start: date = datetime(2019, 11, 1)
    date_application_end: Optional[date] = None


def get_regulation_checks():
    return [
        RegulationCheckData(
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            description="La durée du repos quotidien est d'au-moins 10h toutes les 24h (article R. 3312-53, 2° du code des transports)",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(
                    LONG_BREAK_DURATION_IN_HOURS=10,
                )
            ),
        ),
        RegulationCheckData(
            type="maximumWorkDayTime",
            label="Dépassement(s) de la durée maximale du travail quotidien",
            description="La durée du travail quotidien est limitée à 12h (article R. 3312-a51 du code des transports)",
            regulation_rule="dailyWork",
            variables=json.dumps(
                dict(
                    MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS=10,
                    MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS=12,
                    # START_DAY_WORK_HOUR=5,
                )
            ),
        ),
        RegulationCheckData(
            type="minimumWorkDayBreak",
            label="Non-respect(s) du temps de pause",
            description="Lorsque le temps de travail dépasse 6h le temps de pause minimal est de 30 minutes (article L3312-2 du code des transports). Lorsque le temps de travail dépasse 9h le temps de pause minimal passe à 45 minutes. Le temps de pause peut être réparti en périodes d'au-moins 15 minutes.",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(
                    MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN=15,
                    MINIMUM_DURATION_WORK_IN_HOURS_1=6,
                    MINIMUM_DURATION_WORK_IN_HOURS_2=9,
                    MINIMUM_DURATION_BREAK_IN_MIN_1=30,
                    MINIMUM_DURATION_BREAK_IN_MIN_2=45,
                )
            ),
        ),
        RegulationCheckData(
            type="maximumUninterruptedWorkTime",
            label="Dépassement(s) de la durée maximale du travail ininterrompu",
            description="Lorsque le temps de travail dépasse 6h il doit être interrompu par un temps de pause (article L3312-2 du code des transports)",
            regulation_rule="dailyRest",
            variables=json.dumps(
                dict(MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS=6)
            ),
        ),
        RegulationCheckData(
            type="maximumWorkedDaysInWeek",
            label="Non-respect(s) du repos hebdomadaire",
            description="Il est interdit de travailler plus de six jours dans la semaine (article L. 3132-1 du code du travail). Le repos hebdomadaire doit durer au minimum 34h (article L. 3132-2 du code du travail)",
            regulation_rule="weeklyRest",
            variables=json.dumps(dict()),
        ),
    ]
