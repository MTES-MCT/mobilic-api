from app.models.base import BaseModel
from app import db


class Company(BaseModel):
    name = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return dict(id=self.id, name=self.name)
