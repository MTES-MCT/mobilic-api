from flask_jwt_extended import current_user
from datetime import datetime

from graphql import GraphQLError
import graphene

from app import app, db
from app.controllers.cancel import CancelEvents
from app.controllers.event import (
    preload_or_create_relevant_resources_from_events,
)
from app.controllers.utils import atomic_transaction
from app.data_access.expenditure import ExpenditureOutput
from app.data_access.signup import CompanyOutput
from app.domain.log_expenditures import log_group_expenditure
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    DateTimeWithTimeStampSerialization,
)
from app.models.expenditure import ExpenditureTypes, Expenditure
from app.models.user import User
from app.controllers.event import EventInput


class SingleExpenditureInput(EventInput):
    type = graphene_enum_type(ExpenditureTypes)(required=True)


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
            preload_or_create_relevant_resources_from_events(
                events, User.expenditures
            )
            for group_expenditure in events:
                log_group_expenditure(
                    submitter=current_user,
                    users=[
                        User.query.get(uid)
                        for uid in group_expenditure.user_ids
                    ],
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
