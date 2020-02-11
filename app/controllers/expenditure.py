from flask_jwt_extended import current_user
from typing import List
from datetime import datetime
import graphene

from app.controllers.event import preload_relevant_resources_from_events
from app.controllers.utils import atomic_transaction
from app.data_access.expenditure import ExpenditureInputData, ExpenditureOutput
from app.data_access.utils import with_input_from_schema
from app.domain.log_expenditures import log_group_expenditure
from app.helpers.authorization import with_authorization_policy, authenticated
from app.models import Expenditure
from app.models.user import User
from app.models.company import Company


@with_input_from_schema(ExpenditureInputData, many=True)
class ExpenditureLog(graphene.Mutation):
    expenditures = graphene.List(ExpenditureOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, input: List[ExpenditureInputData]):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            events = sorted(input, key=lambda e: e.event_time)
            preload_relevant_resources_from_events(events)
            expenditure_logs = []
            for group_expenditure in events:
                expenditure_logs += log_group_expenditure(
                    submitter=current_user,
                    company=Company.query.get(group_expenditure.company_id),
                    users=[
                        User.query.get(uid)
                        for uid in group_expenditure.user_ids
                    ],
                    type=group_expenditure.type,
                    event_time=group_expenditure.event_time,
                    reception_time=reception_time,
                )

        return ExpenditureInputData(
            expenditures=[
                e for e in expenditure_logs if type(e) is Expenditure
            ]
        )
