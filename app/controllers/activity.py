from flask_restful import Resource
from typing import List
from sqlalchemy.orm import joinedload

from app import db
from app.controllers.utils import parse_request_with_schema, atomic_transaction
from app.data_access.activity import GroupActivityData
from app.domain.log_activities import log_group_activity
from app.models.user import User
from app.models.company import Company
from app.models.activity import Activity


class ActivityController(Resource):
    @parse_request_with_schema(GroupActivityData, many=True)
    def post(self, data: List[GroupActivityData]):
        with atomic_transaction(commit_at_end=True):
            concerned_user_ids = {
                user_id
                for group_activity in data
                for user_id in group_activity.user_ids
            }
            concerned_submitter_ids = {
                group_activity.submitter_id for group_activity in data
            }
            User.query.options(joinedload(User.activities)).filter(
                User.id.in_(list(concerned_user_ids | concerned_submitter_ids))
            ).all()

            Company.query.filter(
                Company.id.in_(
                    [group_activity.company_id for group_activity in data]
                )
            ).all()
            for group_activity in data:
                activity_logs = log_group_activity(
                    submitter=User.query.get(group_activity.submitter_id),
                    company=Company.query.get(group_activity.company_id),
                    users=[
                        User.query.get(uid) for uid in group_activity.user_ids
                    ],
                    type=group_activity.type,
                    event_time=group_activity.event_time,
                    driver=User.query.get(
                        group_activity.user_ids[group_activity.driver_idx]
                    )
                    if group_activity.driver_idx is not None
                    else None,
                )
                for log in activity_logs:
                    if type(log) == Activity:
                        db.session.add(log)
