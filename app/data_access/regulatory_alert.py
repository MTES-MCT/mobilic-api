import json

import graphene
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.regulatory_alert import RegulatoryAlert
from graphene.types.generic import GenericScalar


class RegulatoryAlertOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = RegulatoryAlert
        only_fields = "extra"

    extra = GenericScalar(
        required=False,
        description="Un dictionnaire de données additionnelles.",
    )

    def resolve_extra(
        self,
        info,
    ):
        return json.dumps(self.extra)
