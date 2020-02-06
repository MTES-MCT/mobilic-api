from flask_restful import Resource
from typing import List

from app import db
from app.controllers.utils import parse_request_with_schema, atomic_transaction
from app.data_access.activity import ActivityData
from app.domain.log_activities import log_activity
from app.models.user import User
from app.models.company import Company


class ActivityController(Resource):
    @parse_request_with_schema(ActivityData, many=True)
    def post(self, data: List[ActivityData]):
        with atomic_transaction(commit_at_end=True):
            concerned_user_ids = {
                user_id
                for single_activity_data in data
                for user_id in single_activity_data.user_ids
            }
            concerned_submitter_ids = {
                single_activity_data.submitter_id
                for single_activity_data in data
            }
            all_concerned_users = User.query.filter(
                User.id.in_(list(concerned_user_ids | concerned_submitter_ids))
            )
            all_concerned_user_map = {
                user.id: user for user in all_concerned_users
            }
            companies = Company.query.filter(
                Company.id.in_(
                    [
                        single_activity_data.company_id
                        for single_activity_data in data
                    ]
                )
            )
            company_map = {c.id for c in companies}
            for single_activity_data in data:
                activity_logs = log_activity(
                    submitter=all_concerned_user_map[
                        single_activity_data.submitter_id
                    ],
                    company=company_map[single_activity_data.id],
                    users=[
                        all_concerned_user_map[u_id]
                        for u_id in single_activity_data.user_ids
                    ],
                    activity_type=single_activity_data.type,
                    event_time=single_activity_data.event_time,
                    driver=all_concerned_user_map[
                        single_activity_data.user_ids[
                            single_activity_data.driver_idx
                        ]
                    ]
                    if single_activity_data.driver_idx
                    else None,
                )
                for log in activity_logs:
                    db.session.add(log)
