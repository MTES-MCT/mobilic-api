from flask_jwt_extended import current_user
from typing import List
from sqlalchemy.orm import joinedload
import graphene

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
            concerned_user_ids = {
                user_id
                for group_activity in input
                for user_id in group_activity.user_ids
            }
            submitter = current_user
            User.query.options(joinedload(User.activities)).filter(
                User.id.in_(list(concerned_user_ids))
            ).all()

            Company.query.filter(
                Company.id.in_(
                    [group_activity.company_id for group_activity in input]
                )
            ).all()
            activity_logs = []
            for group_activity in input:
                activity_logs += log_group_activity(
                    submitter=submitter,
                    company=Company.query.get(group_activity.company_id),
                    users=[
                        User.query.get(uid) for uid in group_activity.user_ids
                    ],
                    type=group_activity.type,
                    event_time=group_activity.event_time,
                    driver=User.query.get(
                        group_activity.user_ids[group_activity.driver_idx]
                    )
                    if group_activity.driver_idx is not None
                    else None,
                )

        return ActivityLog(
            activities=[a for a in activity_logs if type(a) is Activity]
        )
