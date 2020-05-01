from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.event import EventBaseModel


class Mission(EventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=True)

    expenditures = db.Column(JSONB(none_as_null=True), nullable=True)

    def activities_for(self, user, include_dismisses_and_revisions=False):
        all_activities_for_user = sorted(
            [a for a in user.activities if a.mission == self],
            key=lambda a: a.user_time,
        )
        if not include_dismisses_and_revisions:
            return [a for a in all_activities_for_user if a.is_acknowledged]
        return all_activities_for_user

    @property
    def acknowledged_activities(self):
        return sorted(
            [a for a in self.activities if a.is_acknowledged],
            key=lambda a: a.user_time,
        )

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
