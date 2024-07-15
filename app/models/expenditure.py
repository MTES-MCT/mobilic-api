from enum import Enum
import graphene
from sqlalchemy.orm import backref

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
    TimeStamp,
)
from app.models.event import UserEventBaseModel, Dismissable
from app.models.mixins.user_resolver import ResolveUser
from app.models.utils import enum_column


class ExpenditureType(str, Enum):
    DAY_MEAL = "day_meal"
    NIGHT_MEAL = "night_meal"
    SLEEP_OVER = "sleep_over"
    SNACK = "snack"
    __description__ = """
Enumération des valeurs suivantes.
- "day_meal" : repas midi
- "night_meal" : repas soir
- "sleep_over" : découcher
- "snack" : casse-croûte
"""


class Expenditure(UserEventBaseModel, Dismissable):
    backref_base_name = "expenditures"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("expenditures"))

    type = enum_column(ExpenditureType, nullable=False)

    spending_date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.Constraint(
            "no_duplicate_expenditures_per_user_and_date_and_mission"
        ),
    )

    def __repr__(self):
        return f"<Expenditure [{self.id}] : {self.type.value}>"


class ExpenditureOutput(BaseSQLAlchemyObjectType, ResolveUser):
    class Meta:
        model = Expenditure
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "type",
            "user_id",
            "user",
            "spending_date",
            "submitter_id",
            "submitter",
            "dismiss_author_id",
            "dismiss_author",
            "dismissed_at",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant du frais"
    )
    mission_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la mission à laquelle se rattache le frais",
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    user_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant du travailleur mobile concerné par le frais",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a enregistré le frais",
    )
    type = graphene_enum_type(ExpenditureType)(
        required=True, description="Nature du frais"
    )
    spending_date = graphene.Field(
        graphene.Date,
        required=True,
        description="Date à laquelle le frais a été engagé",
    )
    dismissed_at = graphene.Field(
        TimeStamp,
        description="Horodatage de suppression du frais, si jamais le frais a été effacé",
    )
    dismiss_author_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne qui a effacé le frais, si jamais le frais a été effacé",
    )
