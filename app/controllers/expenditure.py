from flask_jwt_extended import current_user
from datetime import datetime
import graphene

from app.controllers.event import preload_relevant_resources_from_events
from app.controllers.utils import atomic_transaction
from app.data_access.expenditure import ExpenditureOutput
from app.domain.log_expenditures import log_group_expenditure
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
from app.models import Expenditure
from app.models.expenditure import ExpenditureTypes
from app.models.user import User
from app.models.company import Company
from app.controllers.event import EventInput


class SingleExpenditureInput(EventInput):
    type = graphene_enum_type(ExpenditureTypes)(required=True)


class ExpenditureLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleExpenditureInput, required=True)

    expenditures = graphene.List(ExpenditureOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            events = sorted(data, key=lambda e: e.event_time)
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
