from flask import g
from sqlalchemy import event
from sqlalchemy.orm import attributes

from app import app, db
from app.helpers.errors import AuthorizationError
from app.models.support_action_log import SupportActionLog

IMPERSONATION_ALLOWED_TABLES = frozenset(
    {
        "user",
        "employment",
        "company",
        "activity",
        "mission",
        "email",
        "team",
        "team_affiliation",
    }
)

REDACTED_COLUMNS = frozenset(
    {
        "password",
        "ssn",
        "activation_email_token",
        "france_connect_id",
        "france_connect_info",
        "secret",
    }
)


def _get_impersonation_context():
    try:
        impersonate_by = getattr(g, "impersonate_by", None)
    except RuntimeError:
        return None
    if not impersonate_by:
        return None
    impersonated_user_id = getattr(
        g, "impersonated_user_id", None
    )
    return impersonate_by, impersonated_user_id


def _coerce_value(val):
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, (dict, list)):
        return val
    return str(val)


def _serialize_obj(obj):
    result = {}
    for col in obj.__class__.__table__.columns.keys():
        if col in REDACTED_COLUMNS:
            continue
        result[col] = _coerce_value(getattr(obj, col, None))
    return result


def _get_old_values(obj):
    old = {}
    for attr in obj.__class__.__table__.columns.keys():
        if attr in REDACTED_COLUMNS:
            continue
        hist = attributes.get_history(obj, attr)
        if hist.deleted:
            old[attr] = _coerce_value(hist.deleted[0])
    return old or None


def _get_changed_new_values(obj):
    new = {}
    for attr in obj.__class__.__table__.columns.keys():
        if attr in REDACTED_COLUMNS:
            continue
        hist = attributes.get_history(obj, attr)
        if hist.added:
            new[attr] = _coerce_value(hist.added[0])
    return new or None


@event.listens_for(db.session, "before_flush")
def guard_impersonation_scope(
    session, flush_context, instances
):
    ctx = _get_impersonation_context()
    if not ctx:
        return
    if not app.config.get("IMPERSONATION_SCOPE_GUARD", False):
        return

    for objects in (session.new, session.dirty, session.deleted):
        for obj in objects:
            if isinstance(obj, SupportActionLog):
                continue
            table = obj.__class__.__tablename__
            if table not in IMPERSONATION_ALLOWED_TABLES:
                raise AuthorizationError(
                    "Impersonation: write blocked on"
                    f" table '{table}'"
                )


@event.listens_for(db.session, "after_flush")
def log_impersonation_actions(session, flush_context):
    if session.info.get("_is_auditing"):
        return
    ctx = _get_impersonation_context()
    if not ctx:
        return
    impersonate_by, impersonated_user_id = ctx

    session.info["_is_auditing"] = True
    try:
        for obj in list(session.new):
            if isinstance(obj, SupportActionLog):
                continue
            session.add(
                SupportActionLog(
                    support_user_id=impersonate_by,
                    impersonated_user_id=impersonated_user_id,
                    table_name=obj.__class__.__tablename__,
                    row_id=obj.id,
                    action="INSERT",
                    old_values=None,
                    new_values=_serialize_obj(obj),
                )
            )

        for obj in list(session.dirty):
            if isinstance(obj, SupportActionLog):
                continue
            session.add(
                SupportActionLog(
                    support_user_id=impersonate_by,
                    impersonated_user_id=impersonated_user_id,
                    table_name=obj.__class__.__tablename__,
                    row_id=obj.id,
                    action="UPDATE",
                    old_values=_get_old_values(obj),
                    new_values=_get_changed_new_values(obj),
                )
            )

        for obj in list(session.deleted):
            if isinstance(obj, SupportActionLog):
                continue
            session.add(
                SupportActionLog(
                    support_user_id=impersonate_by,
                    impersonated_user_id=impersonated_user_id,
                    table_name=obj.__class__.__tablename__,
                    row_id=obj.id,
                    action="DELETE",
                    old_values=_serialize_obj(obj),
                    new_values=None,
                )
            )
    finally:
        session.info.pop("_is_auditing", None)
