from flask_jwt_extended import current_user
from datetime import datetime
import graphene

from app import app
from app.controllers.event import (
    preload_or_create_relevant_resources_from_events,
)
from app.controllers.utils import atomic_transaction
from app.data_access.activity import ActivityOutput
from app.data_access.signup import CompanyOutput
from app.domain.log_activities import log_group_activity
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
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
    company = graphene.Field(CompanyOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        app.logger.info(
            f"Logging activities submitted by {current_user} of company {current_user.company}"
        )
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            events = sorted(data, key=lambda e: e.event_time)
            preload_or_create_relevant_resources_from_events(events)
            for group_activity in events:
                log_group_activity(
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
            activities=current_user.acknowledged_activities,
            company=current_user.company,
        )
