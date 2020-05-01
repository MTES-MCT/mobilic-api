import graphene

from app.data_access.user import UserOutput
from app.domain.permissions import self_or_company_admin
from app.helpers.authentication import create_access_tokens_for
from app.helpers.authorization import with_authorization_policy
from app.models import User
from app import db, app


class UserSignup(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        company_name_to_resolve = graphene.String(required=True)
        company_id = graphene.Int(required=False)

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
        return UserSignup(user=user, **create_access_tokens_for(user))


class Query(graphene.ObjectType):
    user = graphene.Field(UserOutput, id=graphene.Int(required=True))

    @with_authorization_policy(
        self_or_company_admin, get_target_from_return_value=lambda user: user
    )
    def resolve_user(self, info, id):
        matching_user = User.query.get(id)
        # Set the user in the resolver context so that child resolvers can access it
        info.context.user_being_queried = matching_user
        app.logger.info(f"Sending user data for {matching_user}")
        return matching_user
