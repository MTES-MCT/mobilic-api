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
