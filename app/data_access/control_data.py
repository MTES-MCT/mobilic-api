import datetime

import graphene
from graphene import ObjectType
from graphene.types.generic import GenericScalar

from app.data_access.business import BusinessOutput
from app.data_access.control_bulletin import ControlBulletinFields
from app.data_access.employment import EmploymentOutput
from app.data_access.mission import MissionOutput
from app.data_access.regulation_computation import (
    RegulationComputationByDayOutput,
    get_regulation_check_by_type,
)
from app.domain.control_data import convert_extra_datetime_to_user_tz
from app.domain.regulation_computations import get_regulation_computations
from app.domain.regulations import get_default_business
from app.domain.regulations_per_day import NATINF_32083
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.controller_control import ControllerControl, ControlType
from app.models.regulation_check import RegulationCheckType

# TODO refactor sanction code in regulations_per_day and here for consistency
check_type_by_sanction = {
    "NATINF 23103": RegulationCheckType.NO_LIC,
    "NATINF 11292": RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
    "NATINF 20525": RegulationCheckType.MINIMUM_DAILY_REST,
    "NATINF 32083": RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
    "NATINF 13152": RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK,
    "NATINF 11298": RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK,
}


class ObservedInfraction(ObjectType):
    date = graphene.Field(TimeStamp)
    label = graphene.String(
        description="Nom de la règle du seuil règlementaire"
    )
    description = graphene.String(
        description="Description de la règle du seuil règlementaire"
    )
    type = graphene.String()
    unit = graphene.String()
    sanction = graphene.String()
    extra = GenericScalar(
        required=False,
        description="Un dictionnaire de données additionnelles.",
    )
    is_reportable = graphene.Boolean(
        description="Indique si la sanction est relevable par le contrôleur"
    )
    is_reported = graphene.Boolean(
        description="Indique si le contrôleur a relevé l'alerte ou non"
    )
    business = graphene.Field(
        BusinessOutput,
        description="Type d'activité effectuée par le salarié au moment du calcul du seuil règlementaire",
    )

    @classmethod
    def _get_label_and_description(cls, regulation_check, business, sanction):
        _label = regulation_check.label if regulation_check else ""
        _description = (
            regulation_check.resolve_variables(business=business)[
                "DESCRIPTION"
            ]
            if regulation_check
            else ""
        )
        if sanction == NATINF_32083:
            _label = _label.replace("quotidien", "de nuit")
            night_work_description = regulation_check.resolve_variables(
                business=business
            )["NIGHT_WORK_DESCRIPTION"]
            _description = f"{_description} {night_work_description}"

        return _label, _description

    @classmethod
    def get_dummy_from_regulation_check_and_sanction(
        cls, check_type, sanction, business_id
    ):
        regulation_check = get_regulation_check_by_type(type=check_type)
        if regulation_check is None:
            return None
        business = get_default_business(business_id=business_id)

        _label, _description = cls._get_label_and_description(
            regulation_check=regulation_check,
            business=business,
            sanction=sanction,
        )

        return cls(
            sanction=sanction,
            date=None,
            is_reportable=True,
            is_reported=False,
            label=_label,
            description=_description,
            type=regulation_check.type,
            unit=regulation_check.unit,
            business=business,
        )

    @classmethod
    def from_infraction(cls, infraction, user_id):
        check_type = infraction.get("check_type")
        regulation_check = get_regulation_check_by_type(type=check_type)
        if regulation_check is None:
            return None

        business_id = infraction.get("business_id")
        business = get_default_business(business_id=business_id)

        sanction = infraction.get("sanction")
        _label, _description = cls._get_label_and_description(
            regulation_check=regulation_check,
            business=business,
            sanction=sanction,
        )
        extra = infraction.get("extra", None)
        if extra:
            convert_extra_datetime_to_user_tz(extra, user_id)

        return cls(
            sanction=sanction,
            date=datetime.datetime.fromisoformat(infraction.get("date")),
            is_reportable=infraction.get("is_reportable"),
            is_reported=infraction.get("is_reported"),
            label=_label,
            description=_description,
            type=infraction.get("check_type"),
            unit=infraction.get("check_unit"),
            extra=extra,
            business=business,
        )


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    qr_code_generation_time = graphene.Field(TimeStamp, required=False)
    control_bulletin_creation_time = graphene.Field(TimeStamp, required=False)
    creation_time = graphene.Field(TimeStamp, required=True)
    note = graphene.String(required=False)
    nb_controlled_days = graphene.Field(
        graphene.Int,
        required=False,
        description="Nombre de jours de travail sur lesquels porte le contrôle",
    )

    employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs au moment du contrôle",
    )

    missions = graphene.List(
        MissionOutput,
        mission_id=graphene.Int(
            required=False,
            description="Filtre sur une mission à l'aide de son identifiant",
        ),
        description="Liste des missions de l'utilisateur pendant la période de contrôle.",
    )

    history_start_date = graphene.Field(
        graphene.Date,
        required=True,
        description="Date de début de l'historique pouvant être contrôlé",
    )

    regulation_computations_by_day = graphene.List(
        RegulationComputationByDayOutput,
        submitter_type=graphene_enum_type(SubmitterType)(
            required=False,
            description="Version utilisée pour le calcul des dépassements de seuil",
        ),
        description="Résultats de calcul de seuils règlementaires groupés par jour",
    )

    control_bulletin = graphene.Field(ControlBulletinFields, required=False)

    siren = graphene.String()
    company_address = graphene.String()
    mission_address_begin = graphene.String()
    control_type = graphene.String()
    is_day_page_filled = graphene.Boolean(
        required=False,
        description="Indique si la page du jour est remplie lors du contrôle d'un LIC papier.",
    )
    observed_infractions = graphene.List(
        ObservedInfraction,
        required=False,
        description="Liste des infractions retenues",
    )
    nb_reported_infractions = graphene.Field(
        graphene.Int,
        required=False,
        description="Nombre d'infractions retenues",
    )
    reported_infractions_last_update_time = graphene.Field(
        TimeStamp, required=False
    )

    def resolve_control_type(self, info):
        return ControlType(self.control_type).value

    def resolve_control_bulletin(self, info):
        return self.control_bulletin

    def resolve_employments(
        self,
        info,
    ):
        employments = sorted(
            self.user.active_employments_between(
                self.history_start_date,
                self.history_end_date,
                include_pending_ones=False,
            ),
            key=lambda e: e.start_date,
            reverse=True,
        )
        return employments

    def resolve_missions(self, info, mission_id=None):
        missions, _ = self.user.query_missions_with_limit(
            start_time=self.history_start_date,
            end_time=self.history_end_date,
            limit_fetch_activities=2000,
            max_reception_time=self.qr_code_generation_time,
            mission_id=mission_id,
            include_deleted_missions=True,
        )
        return missions

    def resolve_history_start_date(self, info):
        return self.history_start_date

    def resolve_regulation_computations_by_day(
        self, info, submitter_type=None
    ):
        regulation_computations_by_day = get_regulation_computations(
            user_id=self.user.id,
            start_date=self.history_start_date,
            end_date=self.history_end_date,
            submitter_type=submitter_type,
            grouped_by_day=True,
        )
        return [
            RegulationComputationByDayOutput(
                day=day_, regulation_computations=computations_
            )
            for day_, computations_ in regulation_computations_by_day.items()
        ]

    def resolve_observed_infractions(self, info):
        observed_infractions = []

        if self.control_type in (ControlType.mobilic, ControlType.sans_lic):
            for infraction in self.observed_infractions:
                observed_infractions.append(
                    ObservedInfraction.from_infraction(
                        infraction=infraction, user_id=self.user_id
                    )
                )

        elif self.control_type == ControlType.lic_papier:
            remaining_possible_sanctions = check_type_by_sanction.copy()

            # Only one business for lic papier controls
            business_id = self.control_bulletin.get("business_id")

            # First we handle observed infractions
            if self.observed_infractions is not None:
                for infraction in self.observed_infractions:
                    observed_infractions.append(
                        ObservedInfraction.from_infraction(
                            infraction=infraction, user_id=self.user_id
                        )
                    )

            already_seen_sanctions = [
                infraction.sanction for infraction in observed_infractions
            ]

            # Then, we add remaining possible infractions
            for sanction, check_type in remaining_possible_sanctions.items():
                if sanction in already_seen_sanctions:
                    continue
                observed_infractions.append(
                    ObservedInfraction.get_dummy_from_regulation_check_and_sanction(
                        check_type=check_type,
                        sanction=sanction,
                        business_id=business_id,
                    )
                )

        observed_infractions = [
            i for i in observed_infractions if i is not None
        ]
        return observed_infractions
