import graphene
from flask import redirect, request
from uuid import uuid4
from urllib.parse import quote, urlencode

from app.controllers.utils import atomic_transaction
from app.data_access.user import UserOutput
from app.domain.permissions import self_or_company_admin
from app.domain.user import create_user, get_user_from_fc_info
from app.helpers.authentication import (
    current_user,
    create_access_tokens_for,
    UserTokens,
    UserTokensWithFC,
)
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.errors import UserDoesNotExistError
from app.helpers.france_connect import get_fc_user_info
from app.models import User
from app import app
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

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, **data):
        with atomic_transaction(commit_at_end=True):
            user = create_user(**data)

        return UserTokens(**create_access_tokens_for(user))


class CreateUserLogin(graphene.Mutation):
    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email, utilisée comme identifiant pour la connexion",
        )
        password = graphene.String(required=True, description="Mot de passe")

    Output = UserOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, email, password):
        with atomic_transaction(commit_at_end=True):
            if (
                not current_user.france_connect_id
                or current_user.email
                or current_user.password
            ):
                # TODO : raise proper error
                raise ValueError("User has already a login")

            current_user.email = email
            current_user.password = password

        return current_user


@app.route("/fc/authorize")
def redirect_to_fc_authorize():
    query_params = {
        "state": uuid4().hex,
        "nonce": uuid4().hex,
        "response_type": "code",
        "scope": "openid given_name family_name preferred_username birthdate",
        "client_id": app.config["FC_CLIENT_ID"],
        "acr_values": "eidas3",
    }
    return redirect(
        f"{app.config['FC_URL']}/api/v1/authorize?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


@app.route("/fc/logout")
def redirect_to_fc_logout():
    query_params = {"state": uuid4().hex}
    return redirect(
        f"{app.config['FC_URL']}/api/v1/logout?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


class FranceConnectLogin(graphene.Mutation):
    class Arguments:
        authorization_code = graphene.String(required=True)
        invite_token = graphene.String(
            required=False, description="Lien d'invitation"
        )
        state = graphene.String(required=True)
        original_redirect_uri = graphene.String(required=True)
        create = graphene.Boolean(required=False)

    Output = UserTokensWithFC

    @classmethod
    def mutate(
        cls,
        _,
        info,
        authorization_code,
        original_redirect_uri,
        state,
        invite_token=None,
        create=False,
    ):
        with atomic_transaction(commit_at_end=True):
            fc_user_info, fc_token = get_fc_user_info(
                authorization_code, original_redirect_uri
            )
            user = get_user_from_fc_info(fc_user_info)

            if not create and not user:
                raise UserDoesNotExistError("User does not exist")

            if create and user and user.email:
                # TODO : raise proper error
                raise ValueError("User is already registered")

            if not user:
                user = create_user(
                    first_name=fc_user_info.get("given_name"),
                    last_name=fc_user_info.get("family_name"),
                    invite_token=invite_token,
                    fc_info=fc_user_info,
                )

        return UserTokensWithFC(
            **create_access_tokens_for(user), fc_token=fc_token
        )


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
