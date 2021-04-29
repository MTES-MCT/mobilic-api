from sqlalchemy.orm import backref
from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.address import BaseAddressOutput
from app.models.event import EventBaseModel
from app.models.utils import enum_column


class LocationEntryType(str, Enum):
    MISSION_START_LOCATION = "mission_start_location"
    MISSION_END_LOCATION = "mission_end_location"
    __description__ = """
Enumération des valeurs suivantes.
- "mission_start_location" : lieu de début de mission
- "mission_end_location" : lieu de fin de mission
"""


class LocationEntry(EventBaseModel):
    backref_base_name = "location_entries"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("location_entries"))

    address_id = db.Column(
        db.Integer, db.ForeignKey("address.id"), index=True, nullable=False
    )
    _address = db.relationship("Address")

    company_known_address_id = db.Column(
        db.Integer, db.ForeignKey("company_known_address.id"), nullable=True
    )
    _company_known_address = db.relationship("CompanyKnownAddress")

    kilometer_reading = db.Column(db.Integer, nullable=True)

    kilometer_reading_received_at = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )

    type = enum_column(LocationEntryType, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "mission_id",
            "type",
            name="only_one_location_entry_per_mission_and_type",
        ),
    )

    @property
    def address(self):
        return (
            self._company_known_address.address
            if self._company_known_address
            else self._address
        )


class LocationEntryOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = LocationEntry
        interfaces = (BaseAddressOutput,)
        only_fields = ("kilometer_reading", "id")

    def resolve_alias(self, info):
        return None

    def resolve_name(self, info):
        return self.address.name

    def resolve_postal_code(self, info):
        return self.address.postal_code

    def resolve_city(self, info):
        return self.address.city
