import graphene

from app import db, mailer, app
from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.permissions import company_admin
from app.domain.team import populate_team, handle_mail_to_admin_users
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.models import Employment, Company
from app.models.team import Team


class DeleteTeam(AuthenticatedMutation):
    """
    Suppression d'une équipe.

    Renvoie la nouvelle liste des équipes de l'entreprise.
    """

    class Arguments:
        team_id = graphene.Int(
            required=True,
            description="Identifiant de l'équipe à supprimer",
        )

    Output = CompanyOutput

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
            mail_to_send = []
            handle_mail_to_admin_users(mail_to_send, [], team_to_delete)
            db.session.delete(team_to_delete)
            try:
                if len(mail_to_send) > 0:
                    mailer.send_batch(mail_to_send, _disable_commit=True)
            except Exception as e:
                app.logger.exception(e)

        return Company.query.get(company_id)


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
            description="Identifiants des salariés de cette équipe.",
        )
        admin_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des gestionnaires de cette équipe.",
        )

        known_address_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des adresses préenregistrées qui seront affectées à cette équipe.",
        )

        vehicle_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des véhicules qui seront affectées à cette équipe.",
        )

    Output = CompanyOutput

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
        known_address_ids=None,
        vehicle_ids=None,
    ):
        with atomic_transaction(commit_at_end=True):

            new_team = Team(
                name=name,
                company_id=company_id,
            )

            db.session.add(new_team)
            db.session.flush()
            mail_to_send = populate_team(
                new_team,
                name,
                admin_ids,
                user_ids,
                known_address_ids,
                vehicle_ids,
            )
            try:
                if len(mail_to_send) > 0:
                    mailer.send_batch(mail_to_send, _disable_commit=True)
            except Exception as e:
                app.logger.exception(e)

        return Company.query.get(company_id)


class UpdateTeam(AuthenticatedMutation):
    """
    Mis à jour d'une équipe dans l'entreprise.

    Renvoie la liste des équipes de l'entreprise.
    """

    class Arguments:
        team_id = graphene.Int(
            required=True,
            description="Identifiant de l'équipe à modifier",
        )
        name = graphene.String(required=True, description="Nom de l'équipe")
        user_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des salariés de cette équipe.",
        )
        admin_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des gestionnaires de cette équipe.",
        )

        known_address_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des adresses préenregistrées qui seront affectées à cette équipe.",
        )

        vehicle_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Identifiants des véhicules qui seront affectées à cette équipe.",
        )

    Output = CompanyOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Team.query.get(
            kwargs["team_id"]
        ).company_id,
    )
    def mutate(
        cls,
        _,
        info,
        team_id,
        name,
        user_ids=None,
        admin_ids=None,
        known_address_ids=None,
        vehicle_ids=None,
    ):
        with atomic_transaction(commit_at_end=True):

            team_to_update = Team.query.get(team_id)

            mail_to_send = populate_team(
                team_to_update,
                name,
                admin_ids,
                user_ids,
                known_address_ids,
                vehicle_ids,
            )
            try:
                if len(mail_to_send) > 0:
                    mailer.send_batch(mail_to_send, _disable_commit=True)
            except Exception as e:
                app.logger.exception(e)

        return Company.query.get(team_to_update.company_id)
