from dataclasses import field
from dataclasses_json import config
from typing import List
from marshmallow import fields
from graphene_sqlalchemy import SQLAlchemyObjectType

from app.controllers.utils import request_data_schema
from app.data_access.utils import mm_enum_field
from app.helpers.time import from_timestamp, to_timestamp
from app.models.expenditure import ExpenditureTypes, Expenditure


@request_data_schema
class ExpenditureInputData:
    event_time: int = field(
        metadata=config(
            encoder=to_timestamp, decoder=from_timestamp, mm_field=fields.Int()
        )
    )
    type: str = field(
        metadata=config(mm_field=mm_enum_field(ExpenditureTypes))
    )
    user_ids: List[int]
    company_id: int


class ExpenditureOutput(SQLAlchemyObjectType):
    class Meta:
        model = Expenditure
