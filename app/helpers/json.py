from json import JSONEncoder
from datetime import date, datetime

from app.helpers.time import to_timestamp
from app.models.base import BaseModel


class CustomJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, BaseModel):
            return o.to_dict()
        if isinstance(o, datetime):
            return to_timestamp(o)
        return super().default(o)
