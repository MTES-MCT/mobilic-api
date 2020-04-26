from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import EventBaseModel


class Mission(EventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=True)

    expenditures = db.Column(JSONB(none_as_null=True), nullable=True)

    def activities_for(self, user):
        return [
            a for a in self.activities if a.is_acknowledged and a.user == user
        ]

    def team_at(self, date_time):
        from app.models.activity import ActivityDismissType, ActivityType

        team_mates_added_before = set()
        team_mates_removed_before = set()
        earliest_activity_time = None
        # If a coworker is enrolled during a break activity, his first activity will be a dismissed break
        relevant_activities = [
            a
            for a in self.activities
            if a.is_acknowledged
            or a.dismiss_type
            == ActivityDismissType.BREAK_OR_REST_AS_STARTING_ACTIVITY
        ]
        for activity in relevant_activities:
            if activity.user_time <= date_time:
                team_mates_added_before.add(activity.user)
                if activity.type == ActivityType.REST:
                    team_mates_removed_before.add(activity.user)
            earliest_activity_time = (
                min(activity.user_time, earliest_activity_time)
                if earliest_activity_time
                else activity.user_time
            )

        # If the date is before the mission start we return the very first team
        if date_time < earliest_activity_time:
            return {
                a.user
                for a in relevant_activities
                if a.user_time == earliest_activity_time
            }

        return team_mates_added_before - team_mates_removed_before


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission
