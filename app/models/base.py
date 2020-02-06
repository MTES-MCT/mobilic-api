from sqlalchemy.ext.declarative import declared_attr

from app import db
from datetime import datetime


class BaseModel(db.Model):
    __abstract__ = True

    creation_time = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    @declared_attr
    def id(cls):
        if hasattr(cls, "_generate_id"):
            return db.Column(db.Integer, primary_key=True, autoincrement=False)
        else:
            return db.Column(db.Integer, primary_key=True)

    def __init__(self, **kwargs):
        if hasattr(self, "_generate_id"):
            if "id" not in kwargs:
                generated_id = self._generate_id()
                kwargs = dict(kwargs, id=generated_id)
        super().__init__(**kwargs)

    def update(self, kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Model ${self} has no attribute ${key}")
