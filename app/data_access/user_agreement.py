import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import UserAgreement
from app.models.user_agreement import UserAgreementStatus


class UserAgreementOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = UserAgreement
        only_fields = (
            "user_id",
            "user",
            "cgu_version",
            "status",
            "has_transferred_data",
            "is_blacklisted",
            "expires_at",
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
