import re
import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType
from graphene_sqlalchemy.converter import convert_sqlalchemy_type
from graphene.types import DateTime
from graphql import GraphQLError
from graphql.language import ast
from werkzeug.local import LocalProxy
import datetime
from sqlalchemy import types

from app.helpers.password_policy import is_valid_password
from app.helpers.time import to_timestamp, from_timestamp


class TimeStamp(DateTime):
    """
    Custom graphql type to represent datetimes as unix timestamps
    """

    class Meta:
        description = "Horodatage en nombre de secondes écoulées depuis le 1er janvier 1970 minuit UTC"

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
        if isinstance(node, ast.IntValue) or isinstance(node, ast.StringValue):
            try:
                value = int(node.value)
            except ValueError:
                return None
            return cls.parse_value(value)


@convert_sqlalchemy_type.register(types.DateTime)
def convert_column_to_custom_datetime(type, column, registry=None):
    return TimeStamp


GRAPHENE_ENUM_TYPES = {}


def graphene_enum_type(enum):
    """
    Generates a custom graphql type from an enum class.

    We keep track of all created types to avoid duplicate creations of the same type, which lead to runtime errors
    """
    name = enum.__name__ + "Enum"
    if name in GRAPHENE_ENUM_TYPES:
        return GRAPHENE_ENUM_TYPES[name]

    class GrapheneEnumType(graphene.String):
        class Meta:
            name = enum.__name__ + "Enum"
            description = getattr(
                enum,
                "__description__",
                (f"Valeurs possibles : {', '.join([e.value for e in enum])}"),
            )

        @staticmethod
        def serialize(enum_item):
            return enum_item.value

        @staticmethod
        def parse_value(value):
            for enum_item in enum:
                if enum_item == value:
                    return enum_item
            return None

        @staticmethod
        def parse_literal(node):
            if isinstance(node, ast.StringValue):
                return GrapheneEnumType.parse_value(node.value)

    GRAPHENE_ENUM_TYPES[name] = GrapheneEnumType

    return GrapheneEnumType


class BaseSQLAlchemyObjectType(SQLAlchemyObjectType):
    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, **kwargs):
        try:
            if "name" not in kwargs:
                kwargs["name"] = kwargs["model"].__name__
        except:
            pass
        super().__init_subclass_with_meta__(**kwargs)

    id = graphene.Field(graphene.Int)

    @classmethod
    def is_type_of(cls, root, info):
        if isinstance(root, LocalProxy):
            return cls.is_type_of(root._get_current_object(), info)
        return super().is_type_of(root, info)


def is_valid_email(email):
    regex_email = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if re.fullmatch(regex_email, email):
        return True
    return False


class Email(graphene.String):
    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            if is_valid_email(node.value):
                return node.value
        raise GraphQLError(f"Invalid Email")


class Password(graphene.Scalar):
    @staticmethod
    def serialize(value):
        return value

    @staticmethod
    def parse_literal(node, _variables=None):
        if isinstance(node, ast.StringValue):
            return node.value

    @staticmethod
    def parse_value(value):
        if is_valid_password(value):
            return value
        raise GraphQLError(f"Invalid Password")
