import graphene
from flask import after_this_request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import app, db
from app.controllers.utils import Void
from app.domain.user import (
    increment_user_password_tries,
    reinit_user_password_tries,
)
from app.helpers.authentication import (
    create_access_tokens_for,
    set_auth_cookies,
    UserTokens,
    logout,
    refresh_token,
    wrap_jwt_errors,
    unset_auth_cookies,
)
from app.helpers.authentication_controller import refresh_controller_token
from app.helpers.errors import (
    AuthenticationError,
    BlockedAccountError,
    BadPasswordError,
)
from app.models import User
from app.models.user import UserAccountStatus


class LoginMutation(graphene.Mutation):
    """
    Authentification par email/mot de passe.

    Retourne un jeton d'accès avec une certaine durée de validité et un jeton de rafraichissement
    """

    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, email, password):
        user = User.query.filter(User.email == email).one_or_none()
        if not user or (
            not app.config["DISABLE_PASSWORD_CHECK"] and not user.password
        ):
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )
        elif user.status == UserAccountStatus.BLOCKED_BAD_PASSWORD:
            raise BlockedAccountError
        elif not user.check_password(password):
            increment_user_password_tries(user)
            db.session.commit()
            if user.status == UserAccountStatus.BLOCKED_BAD_PASSWORD:
                raise BlockedAccountError
            raise BadPasswordError(
                f"Wrong email/password combination for email {email}",
                nb_bad_tries=user.nb_bad_password_tries,
                max_possible_tries=app.config[
                    "NB_BAD_PASSWORD_TRIES_BEFORE_BLOCKING"
                ],
            )

        reinit_user_password_tries(user)
        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


class LogoutMutation(graphene.Mutation):
    """
    Invalidation du jeton existant de rafraichissement pour l'utilisateur.

    """

    Output = Void

    @classmethod
    def mutate(cls, _, info):
        logout()
        return Void(success=True)


class RefreshMutation(graphene.Mutation):
    """
    Rafraichissement du jeton d'accès. La requête doit comporter l'en-tête "Authorization: Bearer <JETON_DE_RAFRAICHISSEMENT>"

    Attention, un jeton de rafraichissement ne peut être utilisé qu'une seule fois

    Retourne un nouveau jeton d'accès et un nouveau jeton de rafraichissement
    """

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info):
        return UserTokens(*refresh_token())


@app.route("/token/refresh", methods=["POST"])
@wrap_jwt_errors
@jwt_required(refresh=True)
def rest_refresh_token():
    try:
        identity = get_jwt_identity()
        if identity and identity.get("controller"):
            tokens = refresh_controller_token()
        else:
            tokens = refresh_token()
        return jsonify(tokens), 200
    except AuthenticationError as e:

        @after_this_request
        def unset_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@app.route("/token/logout", methods=["POST"])
def rest_logout():
    @after_this_request
    def unset_cookies(response):
        unset_auth_cookies(response)
        return response

    logout()
    return jsonify({"success": True}), 200
