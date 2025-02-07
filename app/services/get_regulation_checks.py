import json

import sqlalchemy as sa
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from app.domain.regulations_helper import DEFAULT_KEY
from app.models.business import TransportType, BusinessType
from app.models.regulation_check import (
    RegulationCheckType,
    RegulationRule,
    UnitType,
)


@dataclass
class RegulationCheckData:
    id: int
    type: RegulationCheckType
    label: str
    regulation_rule: RegulationRule
    variables: str
    unit: UnitType
    date_application_start: date = datetime(2019, 11, 1)
    date_application_end: Optional[date] = None


DESCRIPTION_MAX_WORK_TRV_FREQUENT = "La durée du travail quotidien est limitée à 10h si l’amplitude de la journée est inférieure à 13h, et à 9h si l’amplitude est supérieure à 13h (article D. 3312-6 du Code des transports). Attention, les dérogations ne sont pas intégrées dans Mobilic."
DESCRIPTION_MAX_WORK_TRV_INFREQUENT = "La durée du travail quotidien est limitée à 10h (article D. 3312-6 du Code des transports). Attention, les dérogations ne sont pas intégrées dans Mobilic."
DESCRIPTION_MAX_WORK_TRV_OTHERS = "La durée du travail quotidien est limitée à 10h si l’amplitude de la journée est inférieure à 12h, et à 9h si l’amplitude est supérieure à 12h (article D. 3312-6 du Code des transports). Attention, les dérogations ne sont pas intégrées dans Mobilic."

REGULATION_CHECK_MAXIMUM_WORK_IN_CALENDAR_WEEK = RegulationCheckData(
    id=6,
    type=RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK,
    label="Dépassement(s) de la durée maximale de travail hebdomadaire sur une semaine civile isolée",
    regulation_rule="weeklyWork",
    variables=dict(
        MAXIMUM_WEEKLY_WORK_IN_HOURS={
            str(TransportType.TRM.name): {
                str(BusinessType.LONG_DISTANCE.name): 56,
                str(BusinessType.SHORT_DISTANCE.name): 52,
                str(BusinessType.SHIPPING.name): 48,
            },
            str(TransportType.TRV.name): 48,
        },
        DESCRIPTION={
            str(TransportType.TRM.name): {
                str(
                    BusinessType.LONG_DISTANCE.name
                ): "La durée de travail hebdomadaire sur une semaine isolée est limitée à 56 heures (article R.3312-50 du Code des transports).",
                str(
                    BusinessType.SHORT_DISTANCE.name
                ): "La durée de travail hebdomadaire sur une semaine isolée est limitée à 52 heures (article R.3312-50 du Code des transports).",
                str(
                    BusinessType.SHIPPING.name
                ): "La durée de travail hebdomadaire sur une semaine isolée est limitée à 48 heures (article R.3312-50 du Code des transports).",
            },
            str(
                TransportType.TRV.name
            ): "La durée de travail hebdomadaire sur une semaine isolée est limitée à 48 heures (article L.3121-20 du Code du travail). Attention, les dérogations ne sont pas intégrées dans Mobilic.",
        },
    ),
    unit=UnitType.WEEK,
)


def get_regulation_checks():
    return [
        RegulationCheckData(
            id=1,
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            regulation_rule="dailyRest",
            variables=dict(
                LONG_BREAK_DURATION_IN_HOURS=10,
                DESCRIPTION="La durée du repos quotidien est d'au moins 10h toutes les 24h (article R. 3312-53, 2° du Code des transports).",
            ),
            unit=UnitType.DAY,
        ),
        RegulationCheckData(
            id=2,
            type="maximumWorkDayTime",
            label="Dépassement(s) de la durée maximale du travail quotidien",
            regulation_rule="dailyWork",
            variables=dict(
                MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS=10,
                MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS={
                    str(TransportType.TRM.name): 12,
                    str(TransportType.TRV.name): 10,
                },
                AMPLITUDE_TRIGGER_IN_HOURS={
                    str(TransportType.TRM.name): None,
                    str(TransportType.TRV.name): {
                        BusinessType.FREQUENT.name: 13,
                        BusinessType.INFREQUENT.name: None,
                        DEFAULT_KEY: 12,
                    },
                },
                MAXIMUM_DURATION_OF_DAY_WORK_IF_HIGH_AMPLITUDE_IN_HOURS=9,
                DESCRIPTION={
                    str(
                        TransportType.TRM.name
                    ): "La durée du travail quotidien est limitée à 12h (article R. 3312-a51 du Code des transports).",
                    str(TransportType.TRV.name): {
                        BusinessType.FREQUENT.name: DESCRIPTION_MAX_WORK_TRV_FREQUENT,
                        BusinessType.INFREQUENT.name: DESCRIPTION_MAX_WORK_TRV_INFREQUENT,
                        DEFAULT_KEY: DESCRIPTION_MAX_WORK_TRV_OTHERS,
                    },
                },
                NIGHT_WORK_DESCRIPTION={
                    str(
                        TransportType.TRM.name
                    ): "Si une partie du travail de la journée s'effectue entre minuit et 5 heures, la durée maximale du travail est réduite à 10 heures (L. 3312-1 du Code des transports).",
                    str(
                        TransportType.TRV.name
                    ): "La durée du travail quotidien compris entre minuit et 5 heures est limitée à 10h (L. 3312-1 du Code des transports).",
                },
            ),
            unit=UnitType.DAY,
        ),
        RegulationCheckData(
            id=3,
            type="minimumWorkDayBreak",
            label="Non-respect(s) du temps de pause",
            regulation_rule="dailyRest",
            variables=dict(
                MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN=15,
                MINIMUM_DURATION_WORK_IN_HOURS_1=6,
                MINIMUM_DURATION_WORK_IN_HOURS_2=9,
                MINIMUM_DURATION_BREAK_IN_MIN_1=30,
                MINIMUM_DURATION_BREAK_IN_MIN_2=45,
                DESCRIPTION="La pause doit intervenir avant la 6e heure de travail ininterrompu et durer au moins 30 minutes lorsque le total des heures travaillées est compris entre 6 et 9 heures, et 45 minutes au-delà de 9 heures de travail par jour. Le temps de pause peut être réparti en périodes d'au moins 15 minutes (L. 3312-2 du Code des transports).",
            ),
            unit=UnitType.DAY,
        ),
        RegulationCheckData(
            id=4,
            type="maximumUninterruptedWorkTime",
            label="Dépassement(s) de la durée maximale du travail ininterrompu",
            regulation_rule="dailyRest",
            variables=dict(
                MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS=6,
                DESCRIPTION="Le temps de travail doit être interrompu par une pause avant la 6e heure consécutive (article L3312-2 du Code des transports).",
            ),
            unit=UnitType.DAY,
        ),
        RegulationCheckData(
            id=5,
            type="maximumWorkedDaysInWeek",
            label="Non-respect(s) du repos hebdomadaire",
            regulation_rule="weeklyRest",
            variables=dict(
                MINIMUM_WEEKLY_BREAK_IN_HOURS=34,
                MAXIMUM_DAY_WORKED_BY_WEEK=6,
                DESCRIPTION="Il est interdit de travailler plus de six jours dans la semaine (article L. 3132-1 du Code du travail). Le repos hebdomadaire doit durer au minimum 34h (article L. 3132-2 du Code du travail).",
            ),
            unit=UnitType.WEEK,
        ),
        REGULATION_CHECK_MAXIMUM_WORK_IN_CALENDAR_WEEK,
        RegulationCheckData(
            id=7,
            type="noLic",
            label="Absence de livret individuel de contrôle à bord",
            regulation_rule=None,
            variables=dict(
                DESCRIPTION="Défaut de documents nécessaires au décompte de la durée du travail (L. 3121-67 du Code du travail et R. 3312-58 du Code des transports + arrêté du 20 juillet 1998)."
            ),
            unit=UnitType.DAY,
        ),
    ]


def update_regulation_check_variables(session):
    regulation_check_data = get_regulation_checks()
    for r in regulation_check_data:
        session.execute(
            sa.text(
                "UPDATE regulation_check SET variables = :variables WHERE type = :type;"
            ),
            dict(
                variables=json.dumps(r.variables),
                type=r.type,
            ),
        )
