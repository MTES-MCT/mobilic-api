from sqlalchemy.orm import joinedload
import graphene

from app.models import User, Company
from app import db
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


def preload_or_create_relevant_resources_from_events(events):
    concerned_user_ids = set()
    concerned_new_users_created = set()
    for event in events:
        event.user_id_or_objs = []
        for possible_user in event.team:
            if (
                not possible_user.id
                and possible_user.first_name
                and possible_user.last_name
            ):
                concerned_new_user_key = (
                    possible_user.first_name + " " + possible_user.last_name
                )
                if not concerned_new_user_key in concerned_new_users_created:
                    new_user = User(
                        first_name=possible_user.first_name,
                        last_name=possible_user.last_name,
                        company_id=event.company_id,
                    )
                    concerned_new_users_created[
                        concerned_new_user_key
                    ] = new_user
                    db.session.add(new_user)
                event.user_id_or_objs.append(
                    concerned_new_users_created[concerned_new_user_key]
                )
            elif possible_user.id:
                event.user_id_or_objs.append(possible_user.id)
                concerned_user_ids.add(possible_user.id)

    db.session.flush()

    User.query.options(joinedload(User.activities)).filter(
        User.id.in_(list(concerned_user_ids))
    ).all()

    for event in events:
        event.user_ids = [
            u_id_or_obj if type(u_id_or_obj) is int else u_id_or_obj.id
            for u_id_or_obj in event.user_id_or_objs
        ]

    Company.query.options(joinedload(Company.users)).filter(
        Company.id.in_(
            [group_activity.company_id for group_activity in events]
        )
    ).all()


class TeamMemberInput(graphene.InputObjectType):
    id = graphene.Int(required=False)
    first_name = graphene.Int(required=False)
    last_name = graphene.Int(required=False)


class EventInput(graphene.InputObjectType):
    event_time = DateTimeWithTimeStampSerialization(required=True)
    team = graphene.List(TeamMemberInput, required=True)
    company_id = graphene.Int(required=True)
