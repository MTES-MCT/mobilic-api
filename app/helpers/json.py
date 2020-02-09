from json import JSONEncoder

from app.models.base import BaseModel


class CustomJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, BaseModel):
            return o.to_dict()
        return super().default(o)
