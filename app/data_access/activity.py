from dataclasses import field
from dataclasses_json import config
from typing import List, Optional
from marshmallow import fields

from app.controllers.utils import request_data_schema
from app.data_access.utils import mm_enum_field
from app.helpers.time import from_timestamp, to_timestamp
from app.models.activity import InputableActivityTypes


@request_data_schema
class GroupActivityData:
    event_time: int = field(
        metadata=config(
            encoder=to_timestamp, decoder=from_timestamp, mm_field=fields.Int()
        )
    )
    type: str = field(
        metadata=config(mm_field=mm_enum_field(InputableActivityTypes))
    )
    user_ids: List[int]
    company_id: int
    driver_idx: Optional[int] = None
