from sqlalchemy.ext.declarative import declared_attr

from app import db


class HasBusiness:
    @declared_attr
    def business_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("business.id"),
            index=False,
            nullable=False,
        )

    @declared_attr
    def business(cls):
        return db.relationship("Business")
