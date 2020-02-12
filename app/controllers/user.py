import graphene
from sqlalchemy.orm import joinedload

from app.data_access.signup import UserOutput
from app.domain.permissions import self_or_company_admin
from app.helpers.authorization import with_authorization_policy
from app.models import User
from app import db


class UserSignup(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        company_id = graphene.Int(required=True)

    user = graphene.Field(UserOutput)

    @classmethod
    def mutate(cls, _, info, **data):
        user = User(**data)
        db.session.add(user)
        db.session.commit()
        return UserSignup(user=user)


class Query(graphene.ObjectType):
    user = graphene.Field(UserOutput, id=graphene.Int(required=True))

    @with_authorization_policy(
        self_or_company_admin, get_target_from_return_value=lambda user: user
    )
    def resolve_user(self, info, id):
        matching_user = User.query.options(joinedload(User.activities)).get(id)
        return matching_user
