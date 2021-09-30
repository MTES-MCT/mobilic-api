from datetime import date, datetime, timedelta
from sqlalchemy.orm import (
    synonym,
    joinedload,
    selectinload,
    contains_eager,
)
from sqlalchemy import desc, or_
from werkzeug.security import generate_password_hash, check_password_hash
from cached_property import cached_property
from uuid import uuid4
from sqlalchemy.dialects.postgresql import JSONB

from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.employment import WithEmploymentHistory
from app.helpers.time import VERY_LONG_AGO, VERY_FAR_AHEAD
from app.helpers.validation import validate_email_field_in_db
from app.models.base import BaseModel
from app import db, mailer


class User(BaseModel, WithEmploymentHistory):
    email = db.Column(db.String(255), unique=True, nullable=True, default=None)
    _password = db.Column("password", db.String(255), default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    admin = db.Column(db.Boolean, default=False, nullable=False)
    ssn = db.Column(db.String(13), nullable=True)

    latest_token_revocation_time = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )

    france_connect_id = db.Column(db.String(255), unique=True, nullable=True)
    france_connect_info = db.Column(JSONB(none_as_null=True), nullable=True)

    has_confirmed_email = db.Column(db.Boolean, default=False, nullable=False)
    has_activated_email = db.Column(db.Boolean, default=False, nullable=False)

    activation_email_token = db.Column(
        db.String(128), unique=True, nullable=True, default=None
    )
    subscribed_mailing_lists = db.Column(
        db.ARRAY(db.TEXT), nullable=False, default=[]
    )

    db.validates("email")(validate_email_field_in_db)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, plain_text):
        if plain_text:
            password_hash = generate_password_hash(plain_text.encode("utf8"))
            self._password = password_hash

    def check_password(self, plain_text):
        return check_password_hash(self.password, plain_text.encode("utf-8"))

    password = synonym("_password", descriptor=password)

    @staticmethod
    def _generate_id():
        while True:
            id_ = int(str(uuid4().int)[:9])
            if User.query.get(id_) is None:
                return id_

    @property
    def acknowledged_activities(self):
        return sorted(
            [
                activity
                for activity in self.activities
                if not activity.is_dismissed
            ],
            key=lambda a: a.start_time,
        )

    def query_activities_with_relations(
        self,
        include_dismissed_activities=False,
        include_mission_relations=False,
        include_revisions=False,
        start_time=None,
        end_time=None,
        use_subqueries=False,
        restrict_to_company_ids=None,
    ):
        from app.models import Activity, Mission
        from app.models.queries import query_activities, add_mission_relations

        base_query = query_activities(
            include_dismissed_activities=include_dismissed_activities,
            start_time=start_time,
            end_time=end_time,
            user_id=self.id,
        )

        if restrict_to_company_ids:
            base_query = (
                base_query.join(Activity.mission)
                .options(contains_eager(Activity.mission))
                .filter(Mission.company_id.in_(restrict_to_company_ids))
            )

        if include_mission_relations:
            base_query = base_query.options(
                add_mission_relations(
                    selectinload(Activity.mission),
                    include_revisions=include_revisions,
                    use_subqueries=use_subqueries,
                )
            )
        elif include_revisions:
            base_query = base_query.options(joinedload(Activity.versions))

        return base_query

    def query_missions_with_relations(
        self,
        include_dismissed_activities=False,
        include_revisions=False,
        start_time=None,
        end_time=None,
    ):
        from app.models import Activity, Mission
        from app.models.queries import query_activities, add_mission_relations

        mission_ids = (
            query_activities(
                include_dismissed_activities=include_dismissed_activities,
                start_time=start_time,
                end_time=end_time,
                user_id=self.id,
            )
            .with_entities(Activity.mission_id)
            .distinct()
            .all()
        )

        base_query = add_mission_relations(
            Mission.query, include_revisions=include_revisions
        ).filter(Mission.id.in_(mission_ids))

        return base_query

    def activity_at(self, date_time):
        from app.models import Activity

        return Activity.query.filter(
            Activity.user_id == self.id,
            ~Activity.is_dismissed,
            Activity.start_time <= date_time,
            or_(Activity.end_time.is_(None), Activity.end_time >= date_time),
        ).one_or_none()

    def latest_activity_before(self, date_time):
        from app.models import Activity

        return (
            Activity.query.filter(
                Activity.user_id == self.id,
                ~Activity.is_dismissed,
                Activity.start_time < date_time,
                or_(
                    Activity.end_time.is_(None), Activity.end_time < date_time
                ),
            )
            .order_by(desc(Activity.start_time))
            .first()
        )

    def first_activity_after(self, date_time):
        from app.models import Activity

        return (
            Activity.query.filter(
                Activity.user_id == self.id,
                ~Activity.is_dismissed,
                Activity.start_time > (date_time or VERY_LONG_AGO),
            )
            .order_by(Activity.start_time)
            .first()
        )

    def query_missions_with_limit(
        self,
        include_dismissed_activities=False,
        include_revisions=False,
        start_time=None,
        end_time=None,
        restrict_to_company_ids=None,
        additional_activity_filters=None,
        sort_activities=True,
        limit_fetch_activities=None,
    ):
        sorted_missions = []
        missions = set()

        small_query = (
            start_time
            and (end_time or datetime.now()) - start_time
            <= timedelta(days=366)
        ) or (limit_fetch_activities and limit_fetch_activities <= 1500)

        activity_query = self.query_activities_with_relations(
            include_dismissed_activities=include_dismissed_activities,
            include_mission_relations=True,
            include_revisions=include_revisions,
            start_time=start_time,
            end_time=end_time,
            use_subqueries=not small_query,
        )
        if additional_activity_filters:
            activity_query = additional_activity_filters(activity_query)
        if limit_fetch_activities:
            activity_query = activity_query.limit(limit_fetch_activities + 1)
        activities = activity_query.all()
        has_next_page = (
            len(activities) == limit_fetch_activities + 1
            if limit_fetch_activities
            else False
        )
        activities = (
            activities[:limit_fetch_activities]
            if limit_fetch_activities
            else activities
        )

        if sort_activities:
            activities = sorted(
                activities,
                key=lambda a: (a.is_dismissed, a.start_time),
            )

        for a in activities:
            if a.mission not in missions and (
                restrict_to_company_ids is None
                or a.mission.company_id in restrict_to_company_ids
            ):
                sorted_missions.append(a.mission)
                missions.add(a.mission)
        return sorted_missions, has_next_page

    def query_missions(self, **kwargs):
        return self.query_missions_with_limit(
            **kwargs, **{"limit_fetch_activities": None}
        )[0]

    def revoke_all_tokens(self):
        self.latest_token_revocation_time = datetime.now()
        for token in self.refresh_tokens:
            db.session.delete(token)

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User [{self.id}] : {self.display_name}>"

    @property
    def primary_company(self):
        current_primary_employment = self.primary_employment_at(date.today())
        return (
            current_primary_employment.company
            if current_primary_employment
            else None
        )

    def primary_employment_at(self, date_):
        employments = self.active_employments_at(date_)
        primary_employment = [e for e in employments if e.is_primary]
        return primary_employment[0] if primary_employment else None

    @cached_property
    def current_company_ids_with_admin_rights(self):
        return [
            e.company_id
            for e in self.active_employments_at(date.today())
            if e.has_admin_rights
        ]

    def get_user_id(self):
        return self.id

    def create_activation_link(self):
        self.has_activated_email = False
        self.activation_email_token = str(uuid4())

    def subscribe_to_contact_list(self, contact_list):
        if contact_list not in self.subscribed_mailing_lists:
            mailer.subscribe_email_to_contact_list(self.email, contact_list)
            self.subscribed_mailing_lists = [
                *self.subscribed_mailing_lists,
                contact_list,
            ]
            db.session.add(self)
            db.session.commit()

    def unsubscribe_from_contact_list(self, contact_list, remove=False):
        if contact_list in self.subscribed_mailing_lists:
            (
                mailer.remove_email_from_contact_list
                if remove
                else mailer.unsubscribe_email_to_contact_list
            )(self.email, contact_list)
            self.subscribed_mailing_lists = [
                l for l in self.subscribed_mailing_lists if l != contact_list
            ]
            db.session.add(self)
            db.session.commit()
