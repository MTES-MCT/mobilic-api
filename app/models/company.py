from app.models.base import BaseModel
from app import db


class Company(BaseModel):
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Company [{self.id}] : {self.name}>"
