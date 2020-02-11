from dataclasses import field
from dataclasses_json import config
from typing import Optional

from graphene_sqlalchemy import SQLAlchemyObjectType

from app.controllers.utils import request_data_schema
from app.data_access.event import EventInputData
from app.data_access.utils import mm_enum_field
from app.models.activity import InputableActivityTypes, Activity


@request_data_schema
class ActivityInputData(EventInputData):
    type: str = field(
        metadata=config(mm_field=mm_enum_field(InputableActivityTypes))
    )
    driver_idx: Optional[int] = None
    vehicle_registration_number: Optional[str] = None
    mission: Optional[str] = None


class ActivityOutput(SQLAlchemyObjectType):
    class Meta:
        model = Activity
