from marshmallow import fields, validate, ValidationError
import graphene
from graphql import GraphQLError
from graphene.types import generic


def mm_enum_field(enum):
    return fields.Str(validate=validate.OneOf(list(enum)))


def with_input_from_schema(data_class, many=False):
    class MarshmallowDataClassSchemaInput(generic.GenericScalar):
        @staticmethod
        def serialize(dc):
            raise NotImplementedError(
                "You should only use marshmallow schemas for input validation, not output"
            )

        @staticmethod
        def parse_literal(node):
            data = generic.GenericScalar.parse_literal(node)
            return MarshmallowDataClassSchemaInput.parse_value(data)

        @staticmethod
        def parse_value(data):
            try:
                data_class.schema().load(data, many=many)
            except ValidationError as e:
                raise GraphQLError(
                    "Input validation error",
                    extensions=e.normalized_messages(),
                )
            if many:
                if type(data) is list:
                    parsed_data = [data_class.from_dict(item) for item in data]
                else:
                    parsed_data = [data_class.from_dict(data)]
            else:
                parsed_data = data_class.from_dict(data)
            return parsed_data

    def decorator(cls):
        class WithInputFromMarshmallowSchema(cls):
            class Arguments:
                input = graphene.Argument(
                    MarshmallowDataClassSchemaInput, required=True
                )

        return WithInputFromMarshmallowSchema

    return decorator
