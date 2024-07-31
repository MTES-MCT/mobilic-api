import datetime

import graphene

from app.controllers.utils import atomic_transaction
from app.helpers.authorization import with_authorization_policy
from app.helpers.authentication import AuthenticatedMutation
from app.domain.permissions import only_self
from app.helpers.errors import InvalidParamsError
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import UserAgreement
from app.models.user_agreement import UserAgreementStatus


class UserAgreementOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = UserAgreement
        only_fields = (
            "cgu_version",
            "is_blacklisted",
            "answer_date",
        )

    should_accept_cgu = graphene.Field(
        graphene.Boolean,
        description="Indique si l'utilisateur doit accepter les CGUs en vigueur.",
    )
    has_accepted_cgu = graphene.Field(
        graphene.Boolean,
        description="Indique si l'utilisateur a accepté les CGUs en vigueur.",
    )
    has_rejected_cgu = graphene.Field(
        graphene.Boolean,
        description="Indique si l'utilisateur a refusé les CGUs en vigueur.",
    )

    def resolve_should_accept_cgu(self, info):
        return self.status == UserAgreementStatus.PENDING

    def resolve_has_accepted_cgu(self, info):
        return self.status == UserAgreementStatus.ACCEPTED

    def resolve_has_rejected_cgu(self, info):
        return self.status == UserAgreementStatus.REJECTED


class AcceptCgu(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="Identifiant de l'utilisateur qui accepte les CGU",
        )
        cgu_version = graphene.String(
            required=True,
            description="Version des CGU qu'accepte l'utilisateur",
        )

    Output = UserAgreementOutput

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, user_id, cgu_version):
        current_user_agreement = UserAgreement.get(
            user_id=user_id, cgu_version=cgu_version
        )
        if current_user_agreement is None:
            raise InvalidParamsError(
                f"User agreement does not exist for user_id={user_id} and cgu_version={cgu_version}"
            )

        with atomic_transaction(commit_at_end=True):
            current_user_agreement.status = UserAgreementStatus.ACCEPTED
            current_user_agreement.is_blacklisted = False
            current_user_agreement.expired_at = None
            current_user_agreement.answer_date = datetime.datetime.now()
        return current_user_agreement
