from sqlalchemy.orm import joinedload
import graphene

from app.models import User, Company
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


def preload_relevant_resources_from_events(events):
    concerned_user_ids = {
        user_id for event in events for user_id in event.user_ids
    }
    User.query.options(joinedload(User.activities)).filter(
        User.id.in_(list(concerned_user_ids))
    ).all()

    Company.query.filter(
        Company.id.in_(
            [group_activity.company_id for group_activity in events]
        )
    ).all()


class EventInput(graphene.InputObjectType):
    event_time = DateTimeWithTimeStampSerialization(required=True)
    user_ids = graphene.List(graphene.Int, required=True)
    company_id = graphene.Int(required=True)
