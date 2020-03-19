from sqlalchemy.orm import selectinload
from flask_jwt_extended import current_user
import graphene

from app.models import User, TeamEnrollment
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


def preload_relevant_resources_for_event_logging(relevant_relationship):
    User.query.options(selectinload(relevant_relationship)).options(
        selectinload(User.company)
    ).options(
        selectinload(User.submitted_team_enrollments).selectinload(
            TeamEnrollment.user
        )
    ).filter(
        User.id == current_user.id
    ).one()


class TeamMemberInput(graphene.InputObjectType):
    id = graphene.Int(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)


class EventInput(graphene.InputObjectType):
    event_time = DateTimeWithTimeStampSerialization(required=True)
