from sqlalchemy.ext.declarative import declared_attr

from app import db
from datetime import datetime

from app.helpers.db import DateTimeStoredAsUTC


class BaseModel(db.Model):
    __abstract__ = True

    creation_time = db.Column(
        DateTimeStoredAsUTC, nullable=False, default=datetime.now
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

    @classmethod
    def create(cls, **kwargs):
        obj = cls(**kwargs)
        try:
            db.session.add(obj)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        return obj
