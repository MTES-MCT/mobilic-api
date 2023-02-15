from sqlalchemy import true
from sqlalchemy.orm import relationship

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.base import RandomNineIntId, BaseModel
from app.models.team_association_tables import (
    team_vehicle_association_table,
    team_known_address_association_table,
    team_admin_user_association_table,
)


class Team(BaseModel, RandomNineIntId):
    __tablename__ = "team"
    backref_base_name = "teams"

    name = db.Column(db.String(255), nullable=False)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=true, nullable=False
    )
    company = db.relationship("Company", backref="teams")

    admin_users = relationship(
        "User", secondary=team_admin_user_association_table
    )

    vehicles = relationship(
        "Vehicle", secondary=team_vehicle_association_table
    )

    known_addresses = relationship(
        "CompanyKnownAddress", secondary=team_known_address_association_table
    )


class TeamOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Team
        only_fields = ("name",)
