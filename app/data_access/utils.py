from marshmallow import fields, validate


def mm_enum_field(enum):
    return fields.Str(validate=validate.OneOf(list(enum)))
