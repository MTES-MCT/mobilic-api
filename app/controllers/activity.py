from flask_jwt_extended import current_user
from typing import List
from datetime import datetime
import graphene

from app.controllers.event import preload_relevant_resources_from_events
from app.controllers.utils import atomic_transaction
from app.data_access.activity import ActivityInputData, ActivityOutput
from app.data_access.utils import with_input_from_schema
from app.domain.log_activities import log_group_activity
from app.helpers.authorization import with_authorization_policy, authenticated
from app.models import Activity
from app.models.user import User
from app.models.company import Company


@with_input_from_schema(ActivityInputData, many=True)
class ActivityLog(graphene.Mutation):
    activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, input: List[ActivityInputData]):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            events = sorted(input, key=lambda e: e.event_time)
            preload_relevant_resources_from_events(events)
            activity_logs = []
            for group_activity in events:
                activity_logs += log_group_activity(
                    submitter=current_user,
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
            activities=[a for a in activity_logs if type(a) is Activity]
        )
