from flask_jwt_extended import current_user
import graphene

from app import app, db
from app.controllers.cancel import CancelEvents
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.log_expenditures import log_group_expenditure
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
from app.models.expenditure import (
    ExpenditureType,
    Expenditure,
    ExpenditureOutput,
)
from app.models.user import User
from app.controllers.event import EventInput


class SingleExpenditureInput(EventInput):
    type = graphene_enum_type(ExpenditureType)(required=True)


class ExpenditureLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleExpenditureInput, required=True)

    expenditures = graphene.List(ExpenditureOutput)
    company = graphene.Field(CompanyOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging expenditures submitted by {current_user} of company {current_user.company}"
            )
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(User.expenditures)
            for group_expenditure in events:
                log_group_expenditure(
                    submitter=current_user,
                    users=[current_user]
                    + current_user.acknowledged_team_at(
                        group_expenditure.event_time
                    ),
                    type=group_expenditure.type,
                    event_time=group_expenditure.event_time,
                )

        return ExpenditureLog(
            expenditures=current_user.acknowledged_expenditures,
            company=current_user.company,
        )


class CancelExpenditures(CancelEvents):
    model = Expenditure

    expenditures = graphene.List(ExpenditureOutput)

    @classmethod
    def mutate(cls, *args, **kwargs):
        super().mutate(*args, **kwargs)
        return CancelExpenditures(
            expenditures=current_user.acknowledged_expenditures
        )
