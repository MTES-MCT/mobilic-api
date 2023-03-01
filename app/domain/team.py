from app.models import User, CompanyKnownAddress, Vehicle


def populate_team(
    team_to_update, known_address_ids, name, admin_ids, vehicle_ids
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
    if vehicle_ids:
        vehicles = Vehicle.query.filter(
            Vehicle.id.in_(vehicle_ids), Vehicle.company_id == company_id
        ).all()
        team_to_update.vehicles = vehicles
