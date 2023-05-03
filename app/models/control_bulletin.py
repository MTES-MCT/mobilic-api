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
