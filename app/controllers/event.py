from sqlalchemy.orm import joinedload

from app.models import User, Company


def preload_relevant_resources_from_events(events):
    concerned_user_ids = {
        user_id for event in events for user_id in event.user_ids
    }
    User.query.options(joinedload(User.activities)).filter(
        User.id.in_(list(concerned_user_ids))
    ).all()

    Company.query.filter(
        Company.id.in_(
            [group_activity.company_id for group_activity in events]
        )
    ).all()
