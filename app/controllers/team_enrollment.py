from flask_jwt_extended import current_user
import graphene

from app import app
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.data_access.user import UserOutput
from app.domain.log_team_enrollments import enroll, unenroll
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    DateTimeWithTimeStampSerialization,
)
from app.models.team_enrollment import TeamEnrollmentType
from app.models.user import User
from app.controllers.event import EventInput


class SingleTeamEnrollmentInput(EventInput):
    type = graphene_enum_type(TeamEnrollmentType)(required=True)
    action_time = DateTimeWithTimeStampSerialization(required=False)
    user_id = graphene.Int(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)


class TeamEnrollmentLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleTeamEnrollmentInput, required=True)

    coworkers = graphene.List(UserOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Enrolling team mates for {current_user} of company {current_user.company}"
            )
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(
                User.submitted_team_enrollments
            )
            for event in events:
                if event.type == TeamEnrollmentType.ENROLL:
                    enroll(
                        submitter=current_user,
                        user_id=event.user_id,
                        first_name=event.first_name,
                        last_name=event.last_name,
                        event_time=event.event_time,
                        action_time=event.action_time or event.event_time,
                    )
                else:
                    unenroll(
                        submitter=current_user,
                        user_id=event.user_id,
                        event_time=event.event_time,
                        action_time=event.action_time or event.event_time,
                    )

        return TeamEnrollmentLog(coworkers=current_user.enrollable_coworkers)
