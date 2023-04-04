from datetime import date
from cached_property import cached_property
from sqlalchemy.dialects.postgresql import JSONB

from app.helpers.employment import WithEmploymentHistory
from app.helpers.siren import SirenAPIClient
from app.helpers.time import to_datetime
from app.models import User
from app.models.base import BaseModel
from app import db


class Company(BaseModel, WithEmploymentHistory):
    usual_name = db.Column(db.String(255), nullable=False)

    siren = db.Column(db.String(9), unique=False, nullable=True)

    short_sirets = db.Column(db.ARRAY(db.Integer), nullable=True)

    siren_api_info = db.Column(JSONB(none_as_null=True), nullable=True)

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

    __table_args__ = (db.Constraint(name="only_one_company_per_siret"),)

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

    def users_between(self, start, end):
        active_employments = self.active_employments_between(start, end)
        user_ids = [e.user_id for e in active_employments]
        users = User.query.filter(User.id.in_(user_ids))
        return users

    def get_drivers(self, start, end):
        drivers = []
        users = self.users_between(start, end)
        for user in users:
            # a driver can have admin rights
            if user.has_admin_rights(
                self.id
            ) is False or user.first_activity_after(to_datetime(start)):
                drivers.append(user)
        return drivers

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
