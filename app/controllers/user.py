import graphene

from app.data_access.utils import with_input_from_schema
from app.data_access.signup import SignupPostData, UserOutput
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
