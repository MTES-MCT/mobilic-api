from collections import defaultdict

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.event import EventBaseModel


class Mission(EventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=True)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="missions")

    context = db.Column(JSONB(none_as_null=True), nullable=True)

    def activities_for(self, user, include_dismisses_and_revisions=False):
        all_activities_for_user = sorted(
            [a for a in self.activities if a.user_id == user.id],
            key=lambda a: a.start_time,
        )
        if not include_dismisses_and_revisions:
            return [a for a in all_activities_for_user if a.is_acknowledged]
        return all_activities_for_user

    def expenditures_for(self, user):
        return [
            e for e in self.acknowledged_expenditures if e.user_id == user.id
        ]

    @property
    def acknowledged_activities(self):
        return sorted(
            [a for a in self.activities if a.is_acknowledged],
            key=lambda a: a.start_time,
        )

    @property
    def acknowledged_expenditures(self):
        return sorted(
            [e for e in self.expenditures if e.is_acknowledged],
            key=lambda e: e.reception_time,
        )

    def team_mate_status_history(self):
        from app.models.activity import ActivityDismissType, ActivityType

        # If a coworker is enrolled during a break activity, his first activity will be a dismissed break
        relevant_activities = [
            a
            for a in self.activities
            if a.is_acknowledged
            or a.dismiss_type
            == ActivityDismissType.BREAK_OR_REST_AS_STARTING_ACTIVITY
        ]
        relevant_activities = sorted(
            relevant_activities, key=lambda a: a.start_time
        )
        team_changes_by_user = defaultdict(list)
        for activity in relevant_activities:
            user_status_history = team_changes_by_user[activity.user]
            if activity.type == ActivityType.REST:
                if (
                    user_status_history
                    and user_status_history[-1]["is_enrollment"]
                ):
                    user_status_history.append(
                        dict(
                            is_enrollment=False,
                            time=activity.start_time,
                            coworker=activity.user,
                        )
                    )
            else:
                if (
                    not user_status_history
                    or not user_status_history[-1]["is_enrollment"]
                ):
                    user_status_history.append(
                        dict(
                            is_enrollment=True,
                            time=activity.start_time,
                            coworker=activity.user,
                        )
                    )
        return team_changes_by_user

    def team_at(self, date_time):
        activities = self.acknowledged_activities
        if not activities:
            return []
        earliest_activity_time = min([a.start_time for a in activities])
        time = max(date_time, earliest_activity_time)

        all_team_changes = self.team_mate_status_history()
        team_at_time = set()
        for user, user_team_changes in all_team_changes.items():
            user_team_changes_before_time = [
                tc for tc in user_team_changes if tc["time"] <= time
            ]
            if (
                user_team_changes_before_time
                and user_team_changes_before_time[-1]["is_enrollment"]
            ):
                team_at_time.add(user)

        return team_at_time

    def validated_by(self, user):
        return len([v for v in self.validations if v.submitter == user]) > 0
