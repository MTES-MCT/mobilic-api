from flask_jwt_extended import current_user
from datetime import datetime
import graphene

from app.controllers.event import preload_relevant_resources_from_events
from app.controllers.utils import atomic_transaction
from app.data_access.activity import ActivityOutput
from app.domain.log_activities import log_group_activity
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
from app.models import Activity
from app.models.activity import InputableActivityTypes
from app.models.user import User
from app.models.company import Company
from app.controllers.event import EventInput


class SingleActivityInput(EventInput):
    type = graphene_enum_type(InputableActivityTypes)(required=True)
    driver_idx = graphene.Int(required=False)
    vehicle_registration_number = graphene.String(required=False)
    mission = graphene.String(required=False)


class ActivityLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleActivityInput, required=True)

    activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_from_events(events)
            activity_logs = []
            for group_activity in events:
                activity_logs += log_group_activity(
                    submitter=current_user or User.query.get(282382697),
                    company=Company.query.get(group_activity.company_id),
                    users=[
                        User.query.get(uid) for uid in group_activity.user_ids
                    ],
                    type=group_activity.type,
                    event_time=group_activity.event_time,
                    reception_time=reception_time,
                    driver=User.query.get(
                        group_activity.user_ids[group_activity.driver_idx]
                    )
                    if group_activity.driver_idx is not None
                    else None,
                    vehicle_registration_number=group_activity.vehicle_registration_number,
                    mission=group_activity.mission,
                )

        return ActivityLog(
            activities=[
                a
                for a in activity_logs
                if type(a) is Activity and a.id is not None
            ]
        )
