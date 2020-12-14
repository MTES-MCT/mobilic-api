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

    def activities_for(self, user, include_dismissed_activities=False):
        all_activities_for_user = sorted(
            [a for a in self.activities if a.user_id == user.id],
            key=lambda a: (
                a.start_time,
                a.end_time is None,
                a.reception_time,
            ),
        )
        if not include_dismissed_activities:
            return [a for a in all_activities_for_user if not a.is_dismissed]
        return all_activities_for_user

    def current_activity_for_at(self, user, date_time):
        for activity in self.activities_for(user):
            if activity.start_time <= date_time and (
                not activity.end_time or activity.end_time > date_time
            ):
                return activity
        return None

    def expenditures_for(self, user):
        return [
            e for e in self.acknowledged_expenditures if e.user_id == user.id
        ]

    @property
    def acknowledged_activities(self):
        return sorted(
            [a for a in self.activities if not a.is_dismissed],
            key=lambda a: (a.start_time, a.id),
        )

    @property
    def acknowledged_expenditures(self):
        return sorted(
            [e for e in self.expenditures if not e.is_dismissed],
            key=lambda e: e.reception_time,
        )
