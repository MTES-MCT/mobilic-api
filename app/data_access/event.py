from dataclasses import field
from dataclasses_json import config
from typing import List
from marshmallow import fields

from app.controllers.utils import request_data_schema
from app.helpers.time import to_timestamp, from_timestamp


@request_data_schema
class EventInputData:
    event_time: int = field(
        metadata=config(
            encoder=to_timestamp, decoder=from_timestamp, mm_field=fields.Int()
        )
    )
    user_ids: List[int]
    company_id: int
