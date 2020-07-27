import graphene

from app.controllers.utils import atomic_transaction
from app.data_access.user import UserOutput
from app.domain.permissions import self_or_company_admin
from app.helpers.authentication import create_access_tokens_for
from app.helpers.authorization import with_authorization_policy
from app.models import User, Employment
from app import db, app
from app.models.queries import user_query_with_all_relations


class UserSignUp(graphene.Mutation):
    """
    Inscription d'un nouvel utilisateur.

    Retourne l'utilisateur nouvellement créé.
    """

    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email, utilisée comme identifiant pour la connexion",
        )
        password = graphene.String(required=True, description="Mot de passe")
        first_name = graphene.String(required=True, description="Prénom")
        last_name = graphene.String(required=True, description="Nom")
        invite_token = graphene.String(
            required=False, description="Lien d'invitation"
        )
        ssn = graphene.String(
            required=False, description="Numéro de sécurité sociale"
        )

    user = graphene.Field(UserOutput)
    access_token = graphene.String()
    refresh_token = graphene.String()

    @classmethod
    def mutate(cls, _, info, **data):
        with atomic_transaction(commit_at_end=True):
            invite_token = data.pop("invite_token", None)
            user = User(**data)
            db.session.add(user)
            db.session.flush()

            company = None
            if invite_token:
                employment_to_validate = Employment.query.filter(
                    Employment.invite_token == invite_token
                ).one_or_none()

                if not employment_to_validate:
                    app.logger.warning(
                        f"Could not find valid employment matching token {invite_token}"
                    )
                else:
                    employment_to_validate.user_id = user.id
                    employment_to_validate.invite_token = None
                    employment_to_validate.validate_by(user)
                    company = employment_to_validate.company

            message = f"Signed up new user {user}"
            if company:
                message += f" of company {company}"

            app.logger.info(
                message, extra={"post_to_slack": True, "emoji": ":tada:"},
            )

        return UserSignUp(user=user, **create_access_tokens_for(user))


class Query(graphene.ObjectType):
    user = graphene.Field(
        UserOutput,
        id=graphene.Int(required=True),
        description="Consultation des informations d'un utilisateur, notamment ses enregistrements",
    )

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info, id: id
    )
    def resolve_user(self, info, id):
        matching_user = (
            user_query_with_all_relations().filter(User.id == id).one()
        )
        # Set the user in the resolver context so that child resolvers can access it
        info.context.user_being_queried = matching_user
        app.logger.info(f"Sending user data for {matching_user}")
        return matching_user
