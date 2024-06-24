from enum import Enum

from app.models.base import BaseModel
from app.models.utils import enum_column


class TransportType(str, Enum):
    TRM = "Marchandises"
    TRV = "Voyageurs"


class BusinessType(str, Enum):
    LONG_DISTANCE = "Longue distance"
    SHORT_DISTANCE = "Courte distance"
    SHIPPING = "Messagerie, Fonds et valeur"
    FREQUENT = "Lignes régulières"
    INFREQUENT = "Occasionnels"


class Business(BaseModel):

    transport_type = enum_column(TransportType, nullable=False)
    business_type = enum_column(BusinessType, nullable=False)

    def __repr__(self):
        return f"<Business {self.transport_type} - {self.business_type}"
