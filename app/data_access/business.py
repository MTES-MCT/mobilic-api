from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import Business


class BusinessOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Business
        only_fields = ("business_type", "transport_type")
