from datetime import datetime

from app import app, db
from app.domain.log_events import check_whether_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.helpers.time import local_to_utc
from app.models import TeamEnrollment
from app.models.activity import ActivityType, Activity, ActivityDismissType
from app.models.team_enrollment import TeamEnrollmentType


def log_group_activity(
    submitter, users, type, event_time, user_time, driver, comment,
):
    for user in users:
        activity = log_activity(
            type=type,
            event_time=event_time,
            user_time=user_time,
            user=user,
            submitter=submitter,
            driver=driver,
            comment=comment,
        )
        check_and_fix_inconsistencies_created_by_new_activity(
            activity, event_time
        )


def _check_and_delete_corrected_log(user, user_time):
    latest_activity_log = user.current_acknowledged_activity
    if latest_activity_log:
        if latest_activity_log.user_time >= user_time:
            app.logger.warn("Activity event is revising previous history")
        elif (
            user_time - latest_activity_log.user_time
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


def check_and_fix_inconsistencies_created_by_new_activity(
    activity, event_time
):
    if activity and not activity.is_dismissed:
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
            and next_activity.driver != previous_activity.driver
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
        revised_next_activity = next_activity.revise(
            dismiss_or_revision_time, type=ActivityType.REST
        )
        if revised_next_activity:
            revised_next_activity.dismiss(
                ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismiss_or_revision_time,
            )
            check_and_fix_neighbour_inconsistencies(
                previous_activity,
                previous_activity.next_acknowledged_activity,
                dismiss_or_revision_time,
            )
    elif (
        previous_activity.type == ActivityType.REST
        and local_to_utc(previous_activity.user_time).date()
        == local_to_utc(next_activity.user_time).date()
    ):
        previous_activity.revise(
            dismiss_or_revision_time, type=ActivityType.BREAK
        )
    elif (
        previous_activity.type == ActivityType.BREAK
        and next_activity.type == ActivityType.REST
    ):
        previous_activity.revise(
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
    submitter, user, type, event_time, user_time, driver, comment=None,
):
    if type == ActivityType.DRIVE:
        # Default to marking the submitter as driver if no driver is provided
        if (driver is None and user == submitter) or user == driver:
            type = ActivityType.DRIVE
        else:
            type = ActivityType.SUPPORT

    # 1. Check that event :
    # - is not ahead in the future
    # - was not already processed
    response_if_event_should_not_be_logged = check_whether_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        type=type,
        user_time=user_time,
        event_history=user.activities,
    )
    if response_if_event_should_not_be_logged:
        return None

    # 2. Assess whether the event submitter is authorized to log for the user
    dismiss_type = None
    if not can_submitter_log_for_user(submitter, user):
        app.logger.warn("Event is submitted from unauthorized user")
        dismiss_type = ActivityDismissType.UNAUTHORIZED_SUBMITTER

    # 3. Quick correction mechanics : if it's two real-time logs in succession, delete the first one
    is_revision = event_time != user_time
    if not dismiss_type and not is_revision:
        _check_and_delete_corrected_log(user, user_time)

    # 4. Log the activity
    activity = Activity(
        type=type,
        event_time=event_time,
        user_time=user_time,
        user=user,
        submitter=submitter,
        driver=driver,
        creation_comment=comment,
    )
    db.session.add(activity)

    # 5. If activity marks the end of the day, release the team
    if (
        not dismiss_type
        and not is_revision
        and type == ActivityType.REST
        and user == submitter
    ):
        for u in submitter.acknowledged_team_at(user_time):
            db.session.add(
                TeamEnrollment(
                    type=TeamEnrollmentType.REMOVE,
                    event_time=user_time,
                    user_time=user_time,
                    user=u,
                    submitter=submitter,
                )
            )

    if dismiss_type:
        activity.dismiss(dismiss_type)

    return activity
