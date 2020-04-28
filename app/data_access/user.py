import graphene

from app.data_access.work_day import WorkDayOutput
from app.domain.permissions import self_or_company_admin
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import User
from app.models.activity import ActivityOutput
from app.models.mission import MissionOutput
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
        return self.missions

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_bookable_vehicles(self, info):
        return self.bookable_vehicles
