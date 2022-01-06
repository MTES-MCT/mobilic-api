from typing import NamedTuple, Optional
from datetime import datetime
from enum import Enum

from app.models import (
    User,
    Activity,
    MissionValidation,
    LocationEntry,
    Expenditure,
)
from app.models.event import Dismissable
from app.models.location_entry import LocationEntryType
from app.templates.filters import (
    format_expenditure_label,
    format_activity_type,
    format_time,
)


class LogActionType(int, Enum):
    DELETE = 1
    UPDATE = 2
    CREATE = 3


class LogAction(NamedTuple):
    time: datetime
    submitter: User
    is_after_employee_validation: bool
    resource: any
    type: LogActionType
    version: any = None

    @property
    def is_validation(self):
        return (
            type(self.resource) is MissionValidation
            and self.type == LogActionType.CREATE
        )

    def text(self, show_dates):
        if self.is_validation:
            return "a validé la mission"

        if type(self.resource) is LocationEntry:
            # Only creations
            return f"a renseigné le lieu de {'début' if self.resource.type == LocationEntryType.MISSION_START_LOCATION else 'fin'} de service : {self.resource.address.format()}"

        if type(self.resource) is Expenditure:
            return f"a {'ajouté' if self.type == LogActionType.CREATE else 'supprimé'} le frais {format_expenditure_label(self.resource.type)}"

        if type(self.resource) is Activity:
            if self.type == LogActionType.CREATE:
                if self.version.end_time:
                    return f"a ajouté l'activité {format_activity_type(self.resource.type)} de {format_time(self.version.start_time, show_dates)} à {format_time(self.version.end_time, show_dates)}"
                return f"s'est mis en {format_activity_type(self.resource.type)} à {format_time(self.version.start_time, show_dates)}"

            if self.type == LogActionType.DELETE:
                if self.resource.end_time:
                    return f"a supprimé l'activité {format_activity_type(self.resource.type)} de {format_time(self.resource.start_time, show_dates)} à {format_time(self.resource.end_time, show_dates)}"
                return f"a supprimé l'activité {format_activity_type(self.resource.type)} démarrée à {format_time(self.resource.start_time, show_dates)}"

            previous_version = self.version.previous_version
            if not self.version.end_time and not previous_version.end_time:
                return f"a décalé l'heure de début de l'activité {format_activity_type(self.resource.type)} de {format_time(previous_version.start_time, show_dates)} à {format_time(self.version.start_time, show_dates)}"
            if not self.version.end_time and previous_version.end_time:
                return f"a repris l'activité {format_activity_type(self.resource.type)}"
            if self.version.end_time and not previous_version.end_time:
                return f"a mis fin à l'activité {format_activity_type(self.resource.type)} à {format_time(self.version.end_time, show_dates)}"
            return f"a modifié la période de l'activité {format_activity_type(self.resource.type)} de {format_time(previous_version.start_time, show_dates)} - {format_time(previous_version.end_time, show_dates)} à {format_time(self.version.start_time, show_dates)} - {format_time(self.version.end_time, show_dates)}"


def actions_history(
    mission, user, show_history_before_employee_validation=True
):
    relevant_resources = [
        mission.start_location,
        mission.end_location,
        *mission.activities_for(user, include_dismissed_activities=True),
        *mission.expenditures_for(user, include_dismissed_expenditures=True),
        *[
            v
            for v in mission.validations
            if v.user_id == user.id or (not v.user_id and v.is_admin)
        ],
    ]

    user_validation = mission.validation_of(user)

    actions = []
    for resource in relevant_resources:
        if resource is not None:
            actions.append(
                LogAction(
                    time=resource.reception_time,
                    submitter=resource.submitter,
                    resource=resource,
                    type=LogActionType.CREATE,
                    is_after_employee_validation=user_validation.reception_time
                    < resource.reception_time
                    if user_validation
                    else False,
                    version=resource.version_at(resource.reception_time)
                    if type(resource) is Activity
                    else None,
                )
            )

            if isinstance(resource, Dismissable) and resource.dismissed_at:
                actions.append(
                    LogAction(
                        time=resource.dismissed_at,
                        submitter=resource.dismiss_author,
                        resource=resource,
                        type=LogActionType.DELETE,
                        is_after_employee_validation=user_validation.reception_time
                        < resource.dismissed_at
                        if user_validation
                        else False,
                    )
                )

            if isinstance(resource, Activity):
                revisions = [
                    v for v in resource.versions if v.version_number > 1
                ]
                for revision in revisions:
                    actions.append(
                        LogAction(
                            time=revision.reception_time,
                            submitter=revision.submitter,
                            resource=resource,
                            type=LogActionType.UPDATE,
                            is_after_employee_validation=user_validation.reception_time
                            < revision.reception_time
                            if user_validation
                            else False,
                            version=revision,
                        )
                    )

    if not show_history_before_employee_validation:
        actions = [a for a in actions if a.is_after_employee_validation]
    return sorted(actions, key=lambda a: (a.time, a.type))
