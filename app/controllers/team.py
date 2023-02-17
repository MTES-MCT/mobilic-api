import graphene

from app import db
from app.controllers.utils import atomic_transaction
from app.data_access.team import TeamOutput
from app.domain.permissions import company_admin
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.helpers.errors import InvalidParamsError
from app.models import Employment, User
from app.models.team import Team


class DeleteTeam(AuthenticatedMutation):
    """
    Suppression d'une équipe.

    Renvoie la nouvelle liste des équipes de l'entreprise.
    """

    class Arguments:
        team_id = graphene.Int(
            required=True,
            description="Identifiant de l'entreprise du véhicule",
        )

    Output = graphene.List(TeamOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Team.query.get(
            kwargs["team_id"]
        ).company_id,
    )
    def mutate(cls, _, info, team_id):
        team_to_delete = Team.query.get(team_id)
        company_id = team_to_delete.company_id

        with atomic_transaction(commit_at_end=True):
            Employment.query.filter(Employment.team_id == team_id).update(
                {"team_id": None}
            )
            db.session.delete(team_to_delete)

        all_teams = Team.query.filter(Team.company_id == company_id).all()

        return all_teams


class CreateTeam(AuthenticatedMutation):
    """
    Ajout d'une nouvelle équipe dans l'entreprise.

    Renvoie la liste des équipes de l'entreprise.
    """

    class Arguments:
        company_id = graphene.Int(
            required=True,
            description="Identifiant de l'entreprise de l'équipe",
        )
        name = graphene.String(required=True, description="Nom de l'équipe")
        user_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des utilisateurs qui feront partie de cette équipe.",
        )
        admin_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des gestionnaire de cette équipe.",
        )

        address_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des adresses qui seront affectées à cette équipe.",
        )

        vehicle_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des véhicules qui seront affectées à cette équipe.",
        )

    Output = graphene.List(TeamOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(
        cls,
        _,
        info,
        company_id,
        name,
        user_ids=None,
        admin_ids=None,
        address_ids=None,
        vehicle_ids=None,
    ):
        with atomic_transaction(commit_at_end=True):

            new_team = Team(
                name=name,
                company_id=company_id,
                # user_ids=user_ids,
                # address_ids=address_ids,
                # vehicle_ids=vehicle_ids,
            )
            if admin_ids:
                admin_users = User.query.filter(User.id.in_(admin_ids))
                for admin_user in admin_users:
                    if not admin_user.has_admin_rights(company_id):
                        raise InvalidParamsError(
                            "At least one of the admin of the team does not have admin right on company."
                        )
                new_team.admin_users.extend(admin_users)
            db.session.add(new_team)

        all_teams = Team.query.filter(Team.company_id == company_id).all()

        return all_teams
