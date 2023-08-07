from app import db
from app.models.base import BaseModel


class ControlLocation(BaseModel):

    department = db.Column(db.String(3), index=True, nullable=False)
    postal_code = db.Column(db.String(5), nullable=False)
    commune = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255), nullable=False)
    greco_code = db.Column(db.String(255), nullable=False)
    greco_label = db.Column(db.String(255), nullable=False)
    greco_extra1 = db.Column(db.String(255), nullable=True)
    greco_extra2 = db.Column(db.String(255), nullable=True)
