from datetime import datetime

from app import app, db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.helpers.time import local_to_utc
from app.models.activity import ActivityType, Activity, ActivityDismissType


def log_group_activity(
    submitter,
    users,
    type,
    event_time,
    start_time,
    driver_idx,
    vehicle_registration_number,
    mission,
):
    activities_per_user = {user: type for user in users}
    if len(users) > 1:
        if type == ActivityType.DRIVE:
            driver = users[driver_idx] if driver_idx is not None else None
            for user in users:
                if user == driver:
                    activities_per_user[user] = ActivityType.DRIVE
                else:
                    activities_per_user[user] = ActivityType.SUPPORT

    for user in users:
        activity = log_activity(
            type=activities_per_user[user],
            event_time=event_time,
            start_time=start_time,
            user=user,
            submitter=submitter,
            vehicle_registration_number=vehicle_registration_number,
            mission=mission,
            team=[u.id for u in users],
            driver_idx=driver_idx,
        )
        if not activity.is_dismissed:
            (
                prev_activity,
                next_activity,
            ) = activity.previous_and_next_acknowledged_activities
            check_and_fix_neighbour_inconsistencies(
                prev_activity, activity, event_time
            )
            check_and_fix_neighbour_inconsistencies(
                activity, next_activity, event_time
            )


def _check_and_delete_corrected_log(user, start_time):
    latest_activity_log = user.current_acknowledged_activity
    if latest_activity_log:
        if latest_activity_log.start_time >= start_time:
            app.logger.warn("Activity event is revising previous history")
        elif (
            start_time - latest_activity_log.start_time
            < app.config["MINIMUM_ACTIVITY_DURATION"]
        ):
            app.logger.info(
                "Event time is close to previous logs, deleting these"
            )
            if latest_activity_log.id is not None:
                db.session.delete(latest_activity_log)
            else:
                db.session.expunge(latest_activity_log)
            # This is a dirty hack to have SQLAlchemy immediately propagate object deletion to parent relations
            latest_activity_log.dismissed_at = True


def check_and_fix_neighbour_inconsistencies(
    previous_activity, next_activity, dismiss_or_revision_time=None
):
    if not next_activity or not next_activity.is_acknowledged:
        return
    if not dismiss_or_revision_time:
        dismiss_or_revision_time = datetime.now()
    if not previous_activity and next_activity.type == ActivityType.REST:
        next_activity.dismiss(
            ActivityDismissType.NO_ACTIVITY_SWITCH, dismiss_or_revision_time
        )
    if not previous_activity or not previous_activity.is_acknowledged:
        return

    db.session.add(previous_activity)
    db.session.add(next_activity)
    if previous_activity.type == next_activity.type:
        if (
            next_activity.type == ActivityType.SUPPORT
            and next_activity.team[next_activity.driver_idx]
            != previous_activity.team[previous_activity.driver_idx]
        ):
            next_activity.is_driver_switch = True
        else:
            next_activity.dismiss(
                ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismiss_or_revision_time,
            )
    elif (
        previous_activity.type == ActivityType.REST
        and next_activity.type == ActivityType.BREAK
    ):
        revised_next_activity = next_activity.update_or_revise(
            dismiss_or_revision_time, type=ActivityType.REST
        )
        revised_next_activity.dismiss(
            ActivityDismissType.NO_ACTIVITY_SWITCH, dismiss_or_revision_time
        )
        check_and_fix_neighbour_inconsistencies(
            previous_activity,
            previous_activity.next_acknowledged_activity,
            dismiss_or_revision_time,
        )
    elif (
        previous_activity.type == ActivityType.REST
        and local_to_utc(previous_activity.start_time).date()
        == local_to_utc(next_activity.start_time).date()
    ):
        previous_activity.update_or_revise(
            dismiss_or_revision_time, type=ActivityType.BREAK
        )
    elif (
        previous_activity.type == ActivityType.BREAK
        and next_activity.type == ActivityType.REST
    ):
        previous_activity.update_or_revise(
            dismiss_or_revision_time, type=ActivityType.REST
        )
        next_activity.dismiss(
            ActivityDismissType.NO_ACTIVITY_SWITCH, dismiss_or_revision_time
        )
        check_and_fix_neighbour_inconsistencies(
            previous_activity,
            previous_activity.next_acknowledged_activity,
            dismiss_or_revision_time,
        )


def log_activity(
    submitter,
    user,
    type,
    event_time,
    start_time,
    vehicle_registration_number,
    mission,
    team,
    driver_idx,
):
    # 1. Check that event :
    # - is not ahead in the future
    # - was not already processed
    response_if_event_should_not_be_logged = check_whether_event_should_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        type=type,
        start_time=start_time,
        event_history=user.activities,
    )
    if response_if_event_should_not_be_logged:
        return

    # 2. Assess whether the event submitter is authorized to log for the user
    dismiss_type = None
    if not can_submitter_log_for_user(submitter, user):
        app.logger.warn("Event is submitted from unauthorized user")
        dismiss_type = ActivityDismissType.UNAUTHORIZED_SUBMITTER

    # 3. Quick correction mechanics : if it's two real-time logs in succession, delete the first one
    is_revision = event_time != start_time
    if not dismiss_type and not is_revision:
        _check_and_delete_corrected_log(user, start_time)

    # 4. Log the activity
    activity = Activity(
        type=type,
        event_time=event_time,
        start_time=start_time,
        user=user,
        company_id=submitter.company_id,
        submitter=submitter,
        vehicle_registration_number=vehicle_registration_number,
        mission=mission,
        team=team,
        driver_idx=driver_idx,
    )
    db.session.add(activity)

    if dismiss_type:
        activity.dismiss(dismiss_type)

    return activity
