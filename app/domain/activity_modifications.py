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
    AFTERWARDS_CREATION = "afterwards_creation"


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


def build_activity_modification_list(user):
    all_relevant_activities = [
        a
        for a in user.activities
        if a.authorized_submit
        and a.event_time != a.dismissed_at
        and all([a2.event_time != a.event_time for a2 in a.revised_by])
    ]
    activity_create_or_updates_with_user_action_time = [
        (a.event_time, False, a) for a in all_relevant_activities
    ]

    activity_dismisses_with_user_action_time = [
        (a.dismissed_at, True, a)
        for a in all_relevant_activities
        if a.is_dismissed
    ]

    all_activity_actions_sorted_by_user_action_time = sorted(
        activity_create_or_updates_with_user_action_time
        + activity_dismisses_with_user_action_time,
        key=lambda act_tuple: act_tuple[0],
    )

    activity_modifications = []
    for (
        event_time,
        is_cancel,
        activity,
    ) in all_activity_actions_sorted_by_user_action_time:
        if not is_cancel:
            if activity.revisee:
                revision_type = (
                    ActivityModificationType.TIME_CHANGE
                    if activity.user_time != activity.revisee.user_time
                    else ActivityModificationType.TYPE_CHANGE
                )
                activity_modifications.append(
                    ActivityModification(
                        event_time=event_time,
                        type=revision_type,
                        activity_type=activity.revisee.type,
                        activity_start_time=activity.revisee.user_time,
                        new_activity_start_time=activity.user_time,
                        new_activity_type=activity.type,
                    )
                )
            else:
                activity_modifications.append(
                    ActivityModification(
                        event_time=event_time,
                        type=ActivityModificationType.CREATION
                        if activity.event_time == activity.user_time
                        else ActivityModificationType.AFTERWARDS_CREATION,
                        activity_start_time=activity.user_time,
                        activity_type=activity.type,
                    )
                )
        else:
            activity_modifications.append(
                ActivityModification(
                    event_time=event_time,
                    type=ActivityModificationType.USER_CANCEL
                    if activity.dismiss_type == ActivityDismissType.USER_CANCEL
                    else ActivityModificationType.AUTOMATIC_DISMISS,
                    activity_start_time=activity.user_time,
                    activity_type=activity.type,
                )
            )

    return activity_modifications
