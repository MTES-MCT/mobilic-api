import graphene

from app import db
from app.controllers.utils import atomic_transaction
from app.data_access.team import TeamOutput
from app.domain.permissions import company_admin
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.models.team import Team


class CreateTeam(AuthenticatedMutation):
    """
    Ajout d'une nouvelle équipe dans l'entreprise.

    Renvoie la liste des équipes de l'entreprise.
    """

    class Arguments:
        company_id = graphene.Int(
            required=True,
            description="Identifiant de l'entreprise du véhicule",
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
        user_ids,
        admin_ids,
        address_ids,
        vehicle_ids,
    ):
        with atomic_transaction(commit_at_end=True):

            new_team = Team(
                name=name,
                user_ids=user_ids,
                admin_ids=admin_ids,
                address_ids=address_ids,
                vehicle_ids=vehicle_ids,
            )
            db.session.add(new_team)

            all_teams = Team.query.filter(company_id).all()

        return all_teams
