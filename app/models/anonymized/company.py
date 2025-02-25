# app/models/anonymized/company.py
from app import db
from app.models.anonymized.base import AnonymizedModel
from app.models import Company


class CompanyAnonymized(AnonymizedModel):
    __tablename__ = "company_anonymized"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    allow_team_mode = db.Column(db.Boolean, nullable=False)
    require_kilometer_data = db.Column(db.Boolean, nullable=False)
    require_expenditures = db.Column(db.Boolean, nullable=False)
    require_support_activity = db.Column(db.Boolean, nullable=False)
    require_mission_name = db.Column(db.Boolean, nullable=False)
    allow_transfers = db.Column(db.Boolean, nullable=False)
    accept_certification_communication = db.Column(db.Boolean)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"))

    @classmethod
    def anonymize(cls, company: Company) -> "CompanyAnonymized":
        return cls(
            id=cls.get_new_id("company", company.id),
            creation_time=cls.truncate_to_month(company.creation_time),
            allow_team_mode=company.allow_team_mode,
            require_kilometer_data=company.require_kilometer_data,
            require_expenditures=company.require_expenditures,
            require_support_activity=company.require_support_activity,
            require_mission_name=company.require_mission_name,
            allow_transfers=company.allow_transfers,
            accept_certification_communication=company.accept_certification_communication,
            business_id=cls.get_new_id("business", company.business_id)
            if company.business_id
            else None,
        )
