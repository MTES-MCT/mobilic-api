from flask import request
from werkzeug.datastructures import MultiDict
from marshmallow import ValidationError
from contextlib import contextmanager
from sqlalchemy import event
from dataclasses_json import dataclass_json
from dataclasses import dataclass

from app import db


def request_data_schema(cls):
    return dataclass_json(dataclass(cls))


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
