from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from typing import List, Optional
from datetime import datetime
from marshmallow import fields

from app.data_access.utils import mm_enum_field
from app.helpers.time import from_timestamp, to_timestamp
from app.models.activity import InputableActivityTypes


@dataclass_json
@dataclass
class ActivityData:
    event_time: datetime = field(
        metadata=config(
            encoder=to_timestamp, decoder=from_timestamp, mm_field=fields.Int()
        )
    )
    type: str = field(
        metadata=config(mm_field=mm_enum_field(InputableActivityTypes))
    )
    submitter_id: int
    user_ids: List[int]
    company_id: int
    driver_idx: Optional[int] = None
