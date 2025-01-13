from app.models import Business
from app.models.business import TransportType
from app.models.regulation_check import UnitType, RegulationCheckType


def get_no_lic_observed_infractions(control_date, business_id):
    business = Business.query.get(business_id)

    return [
        {
            "sanction": "NATINF 25666"
            if business.transport_type == TransportType.TRV
            else "NATINF 23103",
            "date": control_date.isoformat(),
            "is_reportable": True,
            "is_reported": True,
            "extra": None,
            "check_unit": UnitType.DAY,
            "check_type": RegulationCheckType.NO_LIC,
            "business_id": business_id,
        }
    ]
