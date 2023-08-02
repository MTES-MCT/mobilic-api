from app.models import ControlLocation


def find_control_location_by_department(department):
    return ControlLocation.query.filter(
        ControlLocation.department == department
    ).all()
