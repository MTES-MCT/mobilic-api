from app.models.regulation_check import UnitType, RegulationCheckType


def get_no_lic_observed_infractions(control_date):
    return [
        {
            "sanction": "NATINF 23103",
            "date": control_date.isoformat(),
            "is_reportable": True,
            "is_reported": True,
            "extra": None,
            "check_unit": UnitType.DAY,
            "check_type": RegulationCheckType.NO_LIC,
        }
    ]
