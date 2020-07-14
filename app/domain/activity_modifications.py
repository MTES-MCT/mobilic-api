from enum import Enum
from datetime import datetime
from typing import NamedTuple, Optional

from app.models.activity import ActivityType, ActivityDismissType


class ActivityModificationType(str, Enum):
    CREATION = "creation"
    USER_CANCEL = "user_cancel"
    AUTOMATIC_DISMISS = "automatic_dismiss"
    TIME_CHANGE = "time_change"
    TYPE_CHANGE = "type_change"


class ActivityModification(NamedTuple):
    event_time: datetime
    type: ActivityModificationType
    activity_type: ActivityType
    activity_start_time: datetime
    activity_end_time: Optional[datetime] = None
    new_activity_type: Optional[ActivityType] = None
    new_activity_start_time: Optional[datetime] = None

    @property
    def is_automatic_or_real_time(self):
        return self.type in [
            ActivityModificationType.CREATION,
            ActivityModificationType.AUTOMATIC_DISMISS,
            ActivityModificationType.TYPE_CHANGE,
        ]


def build_activity_modification_list(activities):
    all_relevant_activities = [
        a
        for a in activities
        if a.reception_time != a.dismissed_at
        and (
            not a.revised_by or a.revised_by.reception_time != a.reception_time
        )  # We discard instant dismisses/revisions which mean that the actual activity event is elsewhere
    ]
    activity_create_or_updates_with_reception_time = [
        (a.reception_time, False, a) for a in all_relevant_activities
    ]

    activity_dismisses_with_reception_time = [
        (a.dismissed_at, True, a)
        for a in all_relevant_activities
        if a.is_dismissed
    ]

    all_activity_actions_sorted_by_user_action_time = sorted(
        activity_create_or_updates_with_reception_time
        + activity_dismisses_with_reception_time,
        key=lambda act_tuple: act_tuple[0],
    )

    activity_modifications = []
    for (
        reception_time,
        is_cancel,
        activity,
    ) in all_activity_actions_sorted_by_user_action_time:
        if not is_cancel:
            if activity.revisee:
                revision_type = (
                    ActivityModificationType.TIME_CHANGE
                    if activity.start_time != activity.revisee.start_time
                    else ActivityModificationType.TYPE_CHANGE
                )
                activity_modifications.append(
                    ActivityModification(
                        event_time=reception_time,
                        type=revision_type,
                        activity_type=activity.revisee.type,
                        activity_start_time=activity.revisee.start_time,
                        new_activity_start_time=activity.start_time,
                        new_activity_type=activity.type,
                    )
                )
            else:
                activity_modifications.append(
                    ActivityModification(
                        event_time=reception_time,
                        type=ActivityModificationType.CREATION,
                        activity_start_time=activity.start_time,
                        activity_type=activity.type,
                    )
                )
        else:
            activity_modifications.append(
                ActivityModification(
                    event_time=reception_time,
                    type=ActivityModificationType.USER_CANCEL
                    if activity.dismiss_type == ActivityDismissType.USER_CANCEL
                    else ActivityModificationType.AUTOMATIC_DISMISS,
                    activity_start_time=activity.start_time,
                    activity_type=activity.type,
                )
            )

    return activity_modifications
