from graphene_sqlalchemy.converter import convert_sqlalchemy_type
from graphene.types import DateTime
import datetime
from sqlalchemy import types

from app.helpers.time import to_timestamp


class DateTimeWithTimeStampSerialization(DateTime):
    @staticmethod
    def serialize(dt):
        assert isinstance(
            dt, (datetime.datetime, datetime.date)
        ), 'Received not compatible datetime "{}"'.format(repr(dt))
        return to_timestamp(dt)


@convert_sqlalchemy_type.register(types.DateTime)
def convert_column_to_custom_datetime(type, column, registry=None):
    return DateTimeWithTimeStampSerialization
