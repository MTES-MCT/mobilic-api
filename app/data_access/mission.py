import graphene
from graphene.types.generic import GenericScalar

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models import Mission
from app.data_access.activity import ActivityOutput
from app.helpers.authentication import current_user
from app.models.comment import CommentOutput
from app.models.controller_control import ControllerControl
from app.models.expenditure import ExpenditureOutput
from app.models.location_entry import LocationEntryType, LocationEntryOutput
from app.models.mission_validation import MissionValidationOutput


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission
        only_fields = (
            "id",
            "reception_time",
            "name",
            "company_id",
            "company",
            "submitter_id",
            "submitter",
            "context",
            "vehicle",
            "vehicle_id",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de la mission"
    )
    name = graphene.Field(graphene.String, description="Nom de la mission")
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    activities = graphene.List(
        ActivityOutput,
        description="Activités de la mission",
        include_dismissed_activities=graphene.Boolean(
            required=False,
            description="Flag pour inclure les activités effacées",
        ),
    )
    context = graphene.Field(
        GenericScalar, description="Données contextuelles libres"
    )
    company_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise qui effectue la mission",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a créé la mission",
    )
    expenditures = graphene.List(
        ExpenditureOutput,
        description="Frais associés la mission",
        include_dismissed_expenditures=graphene.Boolean(
            required=False, description="Flag pour inclure les frais effacés"
        ),
    )
    validations = graphene.List(
        MissionValidationOutput,
        description="Liste des validations de la mission",
    )
    comments = graphene.List(
        CommentOutput, description="Liste des observations de la mission"
    )
    start_location = graphene.Field(
        LocationEntryOutput, description="Lieu de début de la mission"
    )
    end_location = graphene.Field(
        LocationEntryOutput, description="Lieu de fin de la mission"
    )
    is_ended_for_self = graphene.Field(graphene.Boolean)

    def resolve_activities(self, info, include_dismissed_activities=False):
        # TODO à discuter en review
        # if info.context.view_args["max_reception_time"]:

        if (
            info.path[0] == "controlData"
            or info.path[0] == "readMissionControlData"
        ):
            controller_control = ControllerControl.query.get(
                info.variable_values["controlId"]
            )
            max_reception_time = controller_control.qr_code_generation_time
            frozen_activities = list(
                map(
                    lambda a: a.freeze_activity_at(max_reception_time),
                    self.activities,
                )
            )
            return list(
                filter(lambda item: item is not None, frozen_activities)
            )

        return (
            self.activities
            if include_dismissed_activities
            else self.acknowledged_activities
        )

    def resolve_expenditures(self, info, include_dismissed_expenditures=False):
        return (
            self.expenditures
            if include_dismissed_expenditures
            else self.acknowledged_expenditures
        )

    def resolve_validations(self, info):
        return self.validations

    def resolve_comments(self, info):
        return self.acknowledged_comments

    def resolve_start_location(self, info):
        return self.start_location

    def resolve_end_location(self, info):
        return self.end_location

    def resolve_is_ended_for_self(self, info):
        return self.ended_for(current_user)


class MissionConnection(graphene.Connection):
    class Meta:
        node = MissionOutput
