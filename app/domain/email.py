from datetime import datetime, time

from app import db
from app.models import Email


def check_email_exists(email_type, user_id, since_date=None):
    query = db.session.query(Email).filter(
        Email.type == email_type, Email.user_id == user_id
    )
    if since_date:
        query = query.filter(
            Email.creation_time >= datetime.combine(since_date, time())
        )

    return query.first() is not None


def get_warned_user_ids(email_types, cutoff_date):
    """
    Get user IDs who have already been warned via email within the specified timeframe.

    Args:
        email_types: List of email types to check for
        cutoff_date: DateTime to check emails from

    Returns:
        Set of user IDs who have already been warned
    """
    return {
        user_id
        for (user_id,) in db.session.query(Email.user_id)
        .filter(
            Email.type.in_(email_types),
            Email.creation_time >= cutoff_date,
        )
        .all()
    }
