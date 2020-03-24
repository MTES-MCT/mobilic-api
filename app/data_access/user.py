import graphene

from app.data_access.work_day import WorkDayOutput
from app.domain.permissions import self_or_company_admin
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import User
from app.models.activity import ActivityOutput
from app.models.comment import CommentOutput
from app.models.expenditure import ExpenditureOutput
from app.models.mission import MissionOutput
from app.models.team_enrollment import TeamEnrollmentOutput
from app.models.vehicle_booking import VehicleBookingOutput


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
    expenditures = graphene.List(ExpenditureOutput)
    comments = graphene.List(CommentOutput)
    work_days = graphene.List(WorkDayOutput)
    enrollable_coworkers = graphene.List(lambda: UserOutput)
    team_enrollments = graphene.List(TeamEnrollmentOutput)
    missions = graphene.List(MissionOutput)
    vehicle_bookings = graphene.List(VehicleBookingOutput)

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_activities(self, info):
        return self.acknowledged_activities

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_comments(self, info):
        return self.comments

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
    def resolve_team_enrollments(self, info):
        return self.acknowledged_submitted_team_enrollments

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_missions(self, info):
        return self.missions

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_vehicle_bookings(self, info):
        return self.vehicle_bookings
