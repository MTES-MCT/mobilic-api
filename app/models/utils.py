from app import db


def enum_column(enum, **kwargs):
    return db.Column(
        db.Enum(
            enum,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda e: [item.value for item in e],
        ),
        **kwargs,
    )
