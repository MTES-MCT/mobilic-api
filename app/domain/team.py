from app.models import User, CompanyKnownAddress, Vehicle, Employment
from app.models.team import Team
from app.models.team_association_tables import team_vehicle_association_table


def populate_team(
    team_to_update, name, admin_ids, user_ids, known_address_ids, vehicle_ids
):
    company_id = team_to_update.company_id
    team_to_update.name = name
    if admin_ids:
        admin_users = User.query.filter(User.id.in_(admin_ids)).all()
        new_admin_users = [
            u for u in admin_users if u.has_admin_rights(company_id)
        ]
        team_to_update.admin_users = new_admin_users
    else:
        team_to_update.admin_users = []
    if known_address_ids:
        known_addresses = CompanyKnownAddress.query.filter(
            CompanyKnownAddress.id.in_(known_address_ids),
            CompanyKnownAddress.company_id == company_id,
        ).all()
        team_to_update.known_addresses = known_addresses
    else:
        team_to_update.known_addresses = []
    if vehicle_ids:
        vehicles = Vehicle.query.filter(
            Vehicle.id.in_(vehicle_ids), Vehicle.company_id == company_id
        ).all()
        team_to_update.vehicles = vehicles
    else:
        team_to_update.vehicles = []
    Employment.query.filter(Employment.team_id == team_to_update.id).update(
        {"team_id": None}
    )
    if user_ids:
        Employment.query.filter(
            Employment.company_id == company_id,
            Employment.user_id.in_(user_ids),
        ).update({"team_id": team_to_update.id}, synchronize_session=False)


def remove_vehicle_from_all_teams(vehicle):
    teams_with_vehicle = (
        Team.query.join(team_vehicle_association_table)
        .join(Vehicle)
        .filter(
            (team_vehicle_association_table.c.vehicle_id == vehicle.id)
            & (team_vehicle_association_table.c.team_id == Team.id)
        )
        .all()
    )
    for team in teams_with_vehicle:
        team.vehicles.remove(vehicle)
