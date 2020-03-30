import graphene

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.base import BaseModel


class Vehicle(BaseModel):
    registration_number = db.Column(db.TEXT, nullable=False)
    alias = db.Column(db.TEXT, nullable=True)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="vehicles")

    submitter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=False, nullable=False
    )
    submitter = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "registration_number",
            name="unique_registration_numbers_among_company",
        ),
    )

    @property
    def name(self):
        return self.alias or self.registration_number


class VehicleOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Vehicle

    name = graphene.Field(graphene.String)
