import datetime

import graphene

from app import db
from app.controllers.utils import atomic_transaction
from app.data_access.mission import MissionOutput
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.authentication import AuthenticatedMutation, current_user
from app.helpers.authorization import check_company_against_scope_wrapper
from app.helpers.graphene_types import TimeStamp
from app.helpers.time import get_daily_periods
from app.models import Company, Mission, MissionEnd, Comment, User
from app.models.activity import ActivityType


class HolidayLogInput:

    company_id = graphene.Argument(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise pour laquelle la période de congés sera enregistrée.",
    )
    user_id = graphene.Int(
        required=False,
        description="Optionnel, identifiant du salarié concerné par le congé. Par défaut c'est l'auteur de l'opération.",
    )
    start_time = graphene.Argument(
        TimeStamp,
        required=True,
        description="Horodatage du début de la période de congés.",
    )
    end_time = graphene.Argument(
        TimeStamp,
        required=True,
        description="Horodatage de la fin de la période de congés.",
    )
    title = graphene.Argument(
        graphene.String,
        required=True,
        description="Intitulé de la période de congés.",
    )
    comment = graphene.Argument(
        graphene.String,
        required=False,
        description="Précision éventuelle du motif de la période de congés.",
    )


class LogHoliday(AuthenticatedMutation):
    """
    Enregistrement d'un ou plusieurs jours de congés.
    """

    Arguments = HolidayLogInput

    Output = graphene.List(MissionOutput)

    @classmethod
    @check_company_against_scope_wrapper(
        company_id_resolver=lambda *args, **kwargs: kwargs["company_id"]
    )
    def mutate(
        cls,
        _,
        info,
        company_id,
        end_time,
        start_time,
        title,
        user_id=None,
        comment=None,
    ):

        now = datetime.datetime.now()

        user = current_user
        if user_id:
            user = User.query.get(user_id)

        with atomic_transaction(commit_at_end=True):
            company = Company.query.get(company_id)
            periods = get_daily_periods(
                start_date_time=start_time, end_date_time=end_time
            )
            missions = []
            for (start, end) in periods:
                mission = Mission(
                    name=title,
                    company=company,
                    reception_time=now,
                    submitter=current_user,
                )
                db.session.add(mission)
                if comment:
                    db.session.add(
                        Comment(
                            submitter=current_user,
                            mission=mission,
                            text=comment,
                            reception_time=now,
                        )
                    )
                db.session.flush()
                log_activity(
                    submitter=current_user,
                    user=user,
                    type=ActivityType.OFF,
                    mission=mission,
                    switch_mode=False,
                    reception_time=now,
                    start_time=start,
                    end_time=end,
                )
                validate_mission(
                    submitter=current_user,
                    mission=mission,
                    for_user=user,
                )
                missions.append(mission)
        return missions
