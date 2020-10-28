from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.exc import DatabaseError
import graphene

from app import db
from app.helpers.errors import handle_database_error


class Void(graphene.ObjectType):
    success = graphene.Boolean(
        required=True,
        description="Indique si l'opération demandée a bien été effectuée.",
    )


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
        if event.contains(db.session(), "before_commit", _raise_commit_error):
            event.remove(db.session(), "before_commit", _raise_commit_error)
        db.session.rollback()
        if isinstance(e, DatabaseError):
            handle_database_error(e)
        raise e
