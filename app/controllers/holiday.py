import datetime

import graphene

from app import db
from app.controllers.utils import Void, atomic_transaction
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.authentication import AuthenticatedMutation, current_user
from app.helpers.authorization import check_company_against_scope_wrapper
from app.helpers.graphene_types import TimeStamp
from app.models import Company, Mission, MissionEnd, Comment
from app.models.activity import ActivityType


class HolidayLogInput:

    company_id = graphene.Argument(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise pour laquelle la période de repos sera enregistrée.",
    )
    start_time = graphene.Argument(
        TimeStamp,
        required=True,
        description="Horodatage du début de la période de repos.",
    )
    end_time = graphene.Argument(
        TimeStamp,
        required=True,
        description="Horodatage de la fin de la période de repos.",
    )
    title = graphene.Argument(
        graphene.String,
        required=True,
        description="Intitulé de la période de repos.",
    )
    comment = graphene.Argument(
        graphene.String,
        required=False,
        description="Précision éventuelle du motif de la période de repos.",
    )


class LogHoliday(AuthenticatedMutation):
    """
    Enregistrement d'un ou plusieurs jours de repos.
    """

    Arguments = HolidayLogInput

    Output = Void

    @classmethod
    @check_company_against_scope_wrapper(
        company_id_resolver=lambda *args, **kwargs: kwargs["company_id"]
    )
    def mutate(
        cls, _, info, company_id, end_time, start_time, title, comment=None
    ):

        now = datetime.datetime.now()
        with atomic_transaction(commit_at_end=True):
            company = Company.query.get(company_id)

            mission = Mission(
                name=title,
                company=company,
                reception_time=now,
                submitter=current_user,
            )
            if comment:
                Comment(
                    submitter=current_user,
                    mission=mission,
                    text=comment,
                    reception_time=now,
                )
            log_activity(
                submitter=current_user,
                user=current_user,
                type=ActivityType.OFF,
                mission=mission,
                switch_mode=False,
                reception_time=now,
                start_time=start_time,
                end_time=end_time,
            )
            db.session.add(
                MissionEnd(
                    submitter=current_user,
                    reception_time=now,
                    user=current_user,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=current_user,
                mission=mission,
                for_user=current_user,
            )
            return Void(success=True)
