from flask_jwt_extended import current_user
from datetime import datetime

from graphql import GraphQLError
import graphene

from app import app, db
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
                f"Logging activities submitted by {current_user} of company {current_user.company}"
            )
            reception_time = datetime.now()
            events = sorted(data, key=lambda e: e.event_time)
            preload_or_create_relevant_resources_from_events(events)
            for group_expenditure in events:
                log_group_expenditure(
                    submitter=current_user,
                    users=[
                        User.query.get(uid)
                        for uid in group_expenditure.user_ids
                    ],
                    type=group_expenditure.type,
                    event_time=group_expenditure.event_time,
                    reception_time=reception_time,
                )

        return ExpenditureLog(
            expenditures=current_user.acknowledged_expenditures,
            company=current_user.company,
        )


class CancelSingleExpenditureInput(graphene.InputObjectType):
    expenditure_id = graphene.Field(graphene.Int, required=True)
    cancel_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )


class CancelExpenditures(graphene.Mutation):
    class Arguments:
        data = graphene.List(CancelSingleExpenditureInput, required=True)

    expenditures = graphene.List(ExpenditureOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            all_expenditures = Expenditure.query.filter(
                Expenditure.id.in_([e.expenditure_id for e in data])
            ).all()

            if not all(
                [
                    e.submitter_id == current_user.id
                    or e.user_id == current_user.id
                    for e in all_expenditures
                ]
            ):
                raise GraphQLError("Unauthorized")

            for event in data:
                expenditure_matches = [
                    e for e in all_expenditures if e.id == event.expenditure_id
                ]
                if not expenditure_matches:
                    app.logger.warn(
                        f"Could not find expenditures with id {event.expenditure_id} to cancel"
                    )
                else:
                    expenditure_to_cancel = expenditure_matches[0]
                    app.logger.info(
                        f"Cancelling expenditure {expenditure_to_cancel}"
                    )
                    expenditure_to_cancel.cancelled_at = event.cancel_time
                    db.session.add(expenditure_to_cancel)

        return CancelExpenditures(
            expenditures=current_user.acknowledged_expenditures
        )
