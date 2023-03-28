from app import db
from app import mailer
from app.helpers.authentication import current_user
from app.models import User, CompanyKnownAddress, Vehicle, Employment
from app.models.employment import _bind_users_to_team
from app.models.team import Team
from app.models.team_association_tables import (
    team_vehicle_association_table,
    team_known_address_association_table,
    team_admin_user_association_table,
)


def populate_team(
    team_to_update, name, admin_ids, user_ids, known_address_ids, vehicle_ids
):
    company_id = team_to_update.company_id
    team_to_update.name = name
    mail_to_send = []
    new_admin_users = []
    if admin_ids:
        admin_users = User.query.filter(User.id.in_(admin_ids)).all()
        new_admin_users = [
            u for u in admin_users if u.has_admin_rights(company_id)
        ]
    handle_mail_to_admin_users(mail_to_send, new_admin_users, team_to_update)
    team_to_update.admin_users = new_admin_users

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
        _bind_users_to_team(
            user_ids=user_ids, team_id=team_to_update.id, company_id=company_id
        )

    return mail_to_send


def handle_mail_to_admin_users(mail_to_send, new_admin_users, team_to_update):
    newly_affected_users = list(
        set(new_admin_users) - set(team_to_update.admin_users)
    )
    for new_admin in newly_affected_users:
        if current_user.id != new_admin.id:
            mail_to_send.append(
                mailer.generate_team_management_update_mail(
                    user=new_admin,
                    submitter=current_user,
                    team=team_to_update,
                    access_given=True,
                )
            )
        for existing_admin in team_to_update.admin_users:
            if current_user.id != existing_admin.id:
                mail_to_send.append(
                    mailer.generate_team_colleague_affectation_mail(
                        user=existing_admin,
                        new_admin=new_admin,
                        team=team_to_update,
                    )
                )
    removed_admins = list(
        set(team_to_update.admin_users) - set(new_admin_users)
    )
    for former_admin in removed_admins:
        if current_user.id != former_admin.id:
            mail_to_send.append(
                mailer.generate_team_management_update_mail(
                    user=former_admin,
                    submitter=current_user,
                    team=team_to_update,
                    access_given=False,
                )
            )


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


def remove_known_address_from_all_teams(company_known_address):
    teams_with_known_address = (
        Team.query.join(team_known_address_association_table)
        .join(CompanyKnownAddress)
        .filter(
            (
                team_known_address_association_table.c.company_known_address_id
                == company_known_address.id
            )
            & (team_known_address_association_table.c.team_id == Team.id)
        )
        .all()
    )
    for team in teams_with_known_address:
        team.known_addresses.remove(company_known_address)


def remove_admin_from_teams(admin_user_id, company_id):
    team_ids_to_delete = (
        db.session.query(team_admin_user_association_table.c.team_id)
        .join(Team)
        .filter(
            (team_admin_user_association_table.c.user_id == admin_user_id)
            & (Team.company_id == company_id)
        )
        .all()
    )
    if len(team_ids_to_delete) == 0:
        return

    db.session.query(team_admin_user_association_table).filter(
        team_admin_user_association_table.c.user_id == admin_user_id,
        team_admin_user_association_table.c.team_id.in_(
            [item.team_id for item in team_ids_to_delete]
        ),
    ).delete(synchronize_session=False)
