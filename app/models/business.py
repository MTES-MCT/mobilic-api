from enum import Enum

from app.models.base import BaseModel
from app.models.utils import enum_column


class TransportType(str, Enum):
    TRM = "Marchandises"
    TRV = "Voyageurs"


class BusinessType(str, Enum):
    # TRM
    LONG_DISTANCE = "Longue distance"
    SHORT_DISTANCE = "Courte distance"
    SHIPPING = "Messagerie, Fonds et valeur"
    # TRV
    FREQUENT = "Lignes régulières"
    INFREQUENT = "Occasionnels"
    TAXI_GENERAL = "Taxi général"
    TAXI_REGULATED = "Taxi conventionné"
    VTC = "VTC"
    LOTI = "LOTI"


class Business(BaseModel):

    transport_type = enum_column(TransportType, nullable=False)
    business_type = enum_column(BusinessType, nullable=False)

    @property
    def display_name(self):
        return f"{self.transport_type.name} - {self.business_type}"

    def __repr__(self):
        return f"<Business {self.display_name}"
