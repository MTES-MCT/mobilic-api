from flask import request
from werkzeug.datastructures import MultiDict
from marshmallow import ValidationError
from contextlib import contextmanager
from sqlalchemy import event
from app import db


def _convert_data_to_dict(data):
    if (type(data)) is list:
        return data
    if type(data) is dict:
        return data
    if type(data) is MultiDict:
        arg_dict_with_list_values = data.to_dict(flat=False)
        return {
            key: value[0] if len(value) == 1 else value
            for key, value in arg_dict_with_list_values.items()
        }
    raise ValueError("Could not parse input data")


def parse_request_with_schema(data_class, many=False):
    def decorator(method):
        def wrapper(*args, **kwargs):
            data = _convert_data_to_dict(request.data)
            try:
                data_class.schema().load(data, many=many)
            except ValidationError as e:
                raise e
            if many:
                if type(data) is list:
                    parsed_data = [data_class.from_dict(item) for item in data]
                else:
                    parsed_data = [data_class.from_dict(data)]
            else:
                parsed_data = data_class.from_dict(data)
            return method(*args, data=parsed_data, **kwargs)

        return wrapper

    return decorator


def _raise_commit_error(*args, **kwargs):
    raise RuntimeError(
        "Detected a commit attempt inside what is marked as an atomic transaction, aborting."
    )


@contextmanager
def atomic_transaction(commit_at_end=False):
    event.listen(db.session(), "before_commit", _raise_commit_error)
    try:
        yield
        if commit_at_end:
            event.remove(db.session(), "before_commit", _raise_commit_error)
            db.session.commit()
        else:
            db.session.rollback()
            event.remove(db.session(), "before_commit", _raise_commit_error)
    except Exception as e:
        event.remove(db.session(), "before_commit", _raise_commit_error)
        raise e
