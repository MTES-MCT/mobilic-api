from sqlalchemy.orm import joinedload
from flask_jwt_extended import current_user
import graphene

from app.models import User, Company
from app import db, app
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


def preload_or_create_relevant_resources_from_events(events):
    User.query.options(joinedload(User.activities)).options(
        joinedload(User.company).joinedload(Company.users)
    ).filter(
        User.id.in_(
            list([u.id for event in events for u in event.team if u.id])
        )
    ).all()

    new_users_created = dict()
    for event in events:
        event.user_id_or_objs = []
        for possible_user in event.team:
            if (
                not possible_user.id
                and possible_user.first_name
                and possible_user.last_name
            ):
                new_user_key = (
                    possible_user.first_name + " " + possible_user.last_name
                )
                if not new_user_key in new_users_created:
                    new_user = User(
                        first_name=possible_user.first_name,
                        last_name=possible_user.last_name,
                        company_id=current_user.company_id,
                    )
                    app.logger.info(f"Creating new user {new_user}")
                    new_users_created[new_user_key] = new_user
                    db.session.add(new_user)
                event.user_id_or_objs.append(new_users_created[new_user_key])
            elif possible_user.id:
                event.user_id_or_objs.append(possible_user.id)

    db.session.flush()

    for event in events:
        event.user_ids = [
            u_id_or_obj if type(u_id_or_obj) is int else u_id_or_obj.id
            for u_id_or_obj in event.user_id_or_objs
        ]


class TeamMemberInput(graphene.InputObjectType):
    id = graphene.Int(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)


class EventInput(graphene.InputObjectType):
    event_time = DateTimeWithTimeStampSerialization(required=True)
    team = graphene.List(TeamMemberInput, required=True)
