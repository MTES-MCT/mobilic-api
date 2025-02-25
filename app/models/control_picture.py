from app import db
from app.models.base import BaseModel


class ControlPicture(BaseModel):
    control_id = db.Column(
        db.Integer,
        db.ForeignKey("controller_control.id"),
        index=True,
        nullable=False,
    )
    control = db.relationship("ControllerControl", backref="pictures")
    url = db.Column(db.String(255), nullable=False)
