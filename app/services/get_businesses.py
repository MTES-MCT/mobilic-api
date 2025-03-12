from dataclasses import dataclass

from app.models.business import TransportType, BusinessType


@dataclass
class BusinessData:
    id: int
    transport_type: TransportType
    business_type: BusinessType


def get_businesses():
    return [
        BusinessData(
            id=1,
            transport_type=TransportType.TRM,
            business_type=BusinessType.LONG_DISTANCE,
        ),
        BusinessData(
            id=2,
            transport_type=TransportType.TRM,
            business_type=BusinessType.SHORT_DISTANCE,
        ),
        BusinessData(
            id=3,
            transport_type=TransportType.TRM,
            business_type=BusinessType.SHIPPING,
        ),
        BusinessData(
            id=4,
            transport_type=TransportType.TRV,
            business_type=BusinessType.FREQUENT,
        ),
        BusinessData(
            id=5,
            transport_type=TransportType.TRV,
            business_type=BusinessType.INFREQUENT,
        ),
        BusinessData(
            id=6,
            transport_type=TransportType.TRV,
            business_type=BusinessType.TAXI_GENERAL,
        ),
        BusinessData(
            id=7,
            transport_type=TransportType.TRV,
            business_type=BusinessType.TAXI_REGULATED,
        ),
        BusinessData(
            id=8,
            transport_type=TransportType.TRV,
            business_type=BusinessType.VTC,
        ),
        BusinessData(
            id=9,
            transport_type=TransportType.TRV,
            business_type=BusinessType.LOTI,
        ),
    ]
