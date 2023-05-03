from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
)
from app.models import ControlBulletin


class ControlBulletinOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControlBulletin
