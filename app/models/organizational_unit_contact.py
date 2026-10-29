from app.models.base import BaseModel
from app import db


class OrganizationalUnitContact(BaseModel):
    organizational_unit = db.Column(
        db.String(255), unique=True, nullable=False
    )
    address = db.Column(db.String(255), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    siren = db.Column(db.String(9), unique=False, nullable=True)
