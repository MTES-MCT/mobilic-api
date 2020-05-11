import graphene
from datetime import datetime

from app.data_access.mission import MissionOutput
from app.data_access.work_day import WorkDayOutput
from app.domain.permissions import self_or_company_admin
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.authentication import current_user
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    DateTimeWithTimeStampSerialization,
)
from app.models import User
from app.models.activity import ActivityOutput, ActivityType
from app.models.vehicle import VehicleOutput


class UserOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = User
        only_fields = (
            "id",
            "first_name",
            "last_name",
            "company",
            "is_company_admin",
        )

    activities = graphene.List(ActivityOutput)
    work_days = graphene.List(WorkDayOutput)
    enrollable_coworkers = graphene.List(lambda: UserOutput)
    missions = graphene.List(MissionOutput)
    bookable_vehicles = graphene.List(VehicleOutput)
    joined_current_mission_at = graphene.Field(
        DateTimeWithTimeStampSerialization
    )
    left_current_mission_at = graphene.Field(
        DateTimeWithTimeStampSerialization
    )

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_activities(self, info):
        return self.acknowledged_activities

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_work_days(self, info):
        return group_user_events_by_day(self)

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_enrollable_coworkers(self, info):
        return self.enrollable_coworkers

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_missions(self, info):
        return self.missions()

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_bookable_vehicles(self, info):
        return self.bookable_vehicles

    def resolve_joined_current_mission_at(self, info):
        if not current_user:
            return None
        latest_user_activity = current_user.latest_acknowledged_activity_at(
            datetime.now()
        )
        latest_mission = (
            latest_user_activity.mission if latest_user_activity else None
        )
        if not latest_mission:
            return None
        user_activities_in_mission = [
            a for a in latest_mission.acknowledged_activities if a.user == self
        ]
        if user_activities_in_mission:
            return user_activities_in_mission[0].user_time
        return None

    def resolve_left_current_mission_at(self, info):
        if not current_user:
            return None
        latest_user_activity = current_user.latest_acknowledged_activity_at(
            datetime.now()
        )
        latest_mission = (
            latest_user_activity.mission if latest_user_activity else None
        )
        if not latest_mission:
            return None
        user_activities_in_mission = [
            a for a in latest_mission.acknowledged_activities if a.user == self
        ]
        if (
            user_activities_in_mission
            and user_activities_in_mission[-1].type == ActivityType.REST
        ):
            return user_activities_in_mission[-1].user_time
        return None
