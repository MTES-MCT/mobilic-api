import graphene

from app.data_access.user import UserOutput
from app.domain.permissions import self_or_company_admin
from app.helpers.authentication import create_access_tokens_for
from app.helpers.authorization import with_authorization_policy
from app.models import User
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
        company_name_to_resolve = graphene.String(
            required=True,
            description="Nom de l'entreprise (pour rattachement manuel)",
        )
        company_id = graphene.Int(
            required=False,
            description="Identifiant de l'entreprise (pour rattachement automatique)",
        )

    user = graphene.Field(UserOutput)
    access_token = graphene.String()
    refresh_token = graphene.String()

    @classmethod
    def mutate(cls, _, info, **data):
        if not data.get("company_id"):
            data["company_id"] = 1
        user = User(**data)
        try:
            db.session.add(user)
            db.session.commit()
            app.logger.info(
                f"Signed up new user {user} of company {data.get('company_name_to_resolve', None)}",
                extra={"post_to_slack": True, "emoji": ":tada:"},
            )
        except Exception as e:
            app.logger.exception(f"Error during user signup for {user}")
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
