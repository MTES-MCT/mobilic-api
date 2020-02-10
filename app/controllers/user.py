import graphene
from sqlalchemy.orm import joinedload

from app.data_access.utils import with_input_from_schema
from app.data_access.signup import SignupPostData, UserOutput
from app.domain.permissions import self_or_company_admin
from app.helpers.authorization import with_authorization_policy
from app.models import User
from app import db


@with_input_from_schema(SignupPostData)
class UserSignup(graphene.Mutation):
    user = graphene.Field(UserOutput)

    @classmethod
    def mutate(cls, _, info, input):
        user = User(**input.to_dict())
        db.session.add(user)
        db.session.commit()
        return UserSignup(user=user)


class Query(graphene.ObjectType):
    user = graphene.Field(UserOutput, id=graphene.Int(required=True))

    @with_authorization_policy(
        self_or_company_admin, get_target_from_self=lambda self: self
    )
    def resolve_user(self, info, id):
        matching_user = User.query.options(joinedload(User.activities)).get(id)
        return matching_user
