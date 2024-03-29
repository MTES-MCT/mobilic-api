from sqlalchemy import Table

from app import db
from app.models.base import BaseModel

team_admin_user_association_table = Table(
    "team_admin_user",
    BaseModel.metadata,
    db.Column("team_id", db.ForeignKey("team.id"), primary_key=True),
    db.Column("user_id", db.ForeignKey("user.id"), primary_key=True),
)

team_known_address_association_table = Table(
    "team_known_address",
    BaseModel.metadata,
    db.Column("team_id", db.ForeignKey("team.id"), primary_key=True),
    db.Column(
        "company_known_address_id",
        db.ForeignKey("company_known_address.id"),
        primary_key=True,
    ),
)

team_vehicle_association_table = Table(
    "team_vehicle",
    BaseModel.metadata,
    db.Column("team_id", db.ForeignKey("team.id"), primary_key=True),
    db.Column("vehicle_id", db.ForeignKey("vehicle.id"), primary_key=True),
)
