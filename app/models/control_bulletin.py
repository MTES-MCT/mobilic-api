from app import db
from app.models.base import BaseModel


class ControlBulletin(BaseModel):

    control_id = db.Column(
        db.Integer,
        db.ForeignKey("controller_control.id"),
        index=True,
        nullable=False,
        unique=True,
    )
    control = db.relationship(
        "ControllerControl", back_populates="control_bulletin"
    )
    user_first_name = db.Column(db.String(255), nullable=True)
    user_last_name = db.Column(db.String(255), nullable=True)
    lic_paper_presented = db.Column(db.Boolean, nullable=True)
    user_birth_date = db.Column(db.Date, nullable=True)
    user_nationality = db.Column(db.String(255), nullable=True)
    siren = db.Column(db.String, nullable=True)
    company_name = db.Column(db.String, nullable=True)
    company_address = db.Column(db.String, nullable=True)
    vehicle_registration_number = db.Column(db.String, nullable=True)
    vehicle_registration_country = db.Column(db.String, nullable=True)
    mission_address_begin = db.Column(db.String, nullable=True)
    mission_address_end = db.Column(db.String, nullable=True)
    transport_type = db.Column(db.String, nullable=True)
    articles_nature = db.Column(db.String, nullable=True)
    license_number = db.Column(db.String, nullable=True)
    license_copy_number = db.Column(db.String, nullable=True)
