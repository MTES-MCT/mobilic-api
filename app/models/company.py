from datetime import date
from cached_property import cached_property
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import validates
from sqlalchemy import text, event

from app.helpers.employment import WithEmploymentHistory
from app.helpers.siren import SirenAPIClient
from app.helpers.time import VERY_LONG_AGO
from app.models import User
from app.models.base import BaseModel
from app import db
from app.models.business import BusinessType
from app.models.mixins.has_business import HasBusiness


class Company(BaseModel, WithEmploymentHistory, HasBusiness):
    usual_name = db.Column(db.String(255), nullable=False)

    siren = db.Column(db.String(9), unique=False, nullable=True)

    short_sirets = db.Column(db.ARRAY(db.Integer), nullable=True)

    siren_api_info = db.Column(JSONB(none_as_null=True), nullable=True)

    phone_number = db.Column(
        db.String(30), unique=False, nullable=True, default=None
    )

    number_workers = db.Column(db.Integer(), nullable=True)

    # Parameters of work day logging
    allow_team_mode = db.Column(db.Boolean, nullable=False, default=True)

    # Temps de liaisons
    allow_transfers = db.Column(db.Boolean, nullable=False, default=False)

    require_kilometer_data = db.Column(
        db.Boolean, nullable=False, default=True
    )
    require_expenditures = db.Column(db.Boolean, nullable=False, default=True)
    require_support_activity = db.Column(
        db.Boolean, nullable=False, default=False
    )
    require_mission_name = db.Column(db.Boolean, nullable=False, default=True)

    allow_other_task = db.Column(db.Boolean, nullable=True)
    other_task_label = db.Column(
        db.String(24), unique=False, nullable=True, default=""
    )

    has_ceased_activity = db.Column(db.Boolean, nullable=False, default=False)

    siren_api_info_last_update = db.Column(db.Date, nullable=False, index=True)

    nb_certificate_badge_request = db.Column(
        db.Integer, default=0, nullable=False
    )

    __table_args__ = (db.Constraint(name="only_one_company_per_siret"),)

    @validates("siren_api_info")
    def validate_siren_api_info(self, key, value):
        """Set last update date whenever `siren_api_info` is modified."""
        self.siren_api_info_last_update = date.today()
        return value

    @property
    def name(self):
        return self.usual_name

    def __repr__(self):
        return f"<Company [{self.id}] : {self.name}>"

    @property
    def users(self):
        today = date.today()
        return [e.user for e in self.active_employments_at(today)]

    @cached_property
    def legal_name(self):
        if self.siren_api_info:
            legal_unit_dict = self.siren_api_info["uniteLegale"]
            return SirenAPIClient._get_legal_unit_name(legal_unit_dict)
        return ""

    def active_users_in_team(self, team_id):
        today = date.today()
        return [
            e.user
            for e in self.active_employments_at(today)
            if e.team_id == team_id
        ]

    def users_ids_between(self, start, end):
        active_employments = self.active_employments_between(start, end)
        return [e.user_id for e in active_employments]

    def users_between(self, start, end):
        active_user_ids = self.users_ids_between(start, end)
        users = User.query.filter(User.id.in_(active_user_ids))
        return users

    def get_admins(self, start, end):
        safe_end = end or date.today()
        safe_start = start or VERY_LONG_AGO.date()

        sql = text(
            """
            SELECT u.*
            FROM "user" u
            JOIN (
                SELECT DISTINCT ON (user_id) *
                FROM employment
                WHERE company_id = :company_id
                AND start_date <= :end
                AND dismissed_at is NULL 
                AND validation_status != 'rejected'
                AND (end_date is NULL OR end_date >= :start)
                ORDER BY user_id, start_date DESC
            ) e ON e.user_id = u.id
            WHERE has_admin_rights is true
            """
        )
        return (
            db.session.query(User)
            .from_statement(sql)
            .params(
                company_id=self.id,
                start=safe_start,
                end=safe_end,
            )
            .all()
        )

    def query_current_users(self):
        from app.models import User

        today = date.today()

        user_ids = [e.user_id for e in self.active_employments_at(today)]
        return User.query.filter(User.id.in_(user_ids))

    @cached_property
    def retrieve_authorized_clients(self):
        return list(
            map(
                lambda filtered_client: filtered_client.client,
                filter(
                    lambda client: not client.is_dismissed,
                    self.authorized_clients_link,
                ),
            )
        )


@event.listens_for(Company, "before_insert")
def set_allow_other_task(mapper, connect, target):
    if target.business:
        target.allow_other_task = (
            target.business.business_type != BusinessType.SHIPPING
        )
