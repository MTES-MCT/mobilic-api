import graphene
from graphene_sqlalchemy.converter import convert_sqlalchemy_type
from graphene.types import DateTime
from graphql.language import ast
import datetime
from sqlalchemy import types

from app.helpers.time import to_timestamp, from_timestamp


class DateTimeWithTimeStampSerialization(DateTime):
    class Meta:
        description = "Unix timestamp in ms"

    @staticmethod
    def serialize(dt):
        return to_timestamp(dt)

    @staticmethod
    def parse_value(value):
        try:
            if isinstance(value, datetime.datetime):
                return value
            return from_timestamp(value)
        except Exception:
            return None

    @classmethod
    def parse_literal(cls, node):
        if isinstance(node, ast.IntValue):
            return cls.parse_value(node.value)


@convert_sqlalchemy_type.register(types.DateTime)
def convert_column_to_custom_datetime(type, column, registry=None):
    return DateTimeWithTimeStampSerialization


GRAPHENE_ENUM_TYPES = {}


def graphene_enum_type(enum):
    name = enum.__name__ + "Enum"
    if name in GRAPHENE_ENUM_TYPES:
        return GRAPHENE_ENUM_TYPES[name]

    class GrapheneEnumType(graphene.String):
        class Meta:
            name = enum.__name__ + "Enum"
            description = f"Values : {', '.join([e.value for e in enum])}"

        @staticmethod
        def serialize(enum_item):
            return enum_item.value

        @staticmethod
        def parse_value(value):
            for enum_item in enum:
                if enum_item == value:
                    return enum_item
            return None

    GRAPHENE_ENUM_TYPES[name] = GrapheneEnumType

    return GrapheneEnumType
