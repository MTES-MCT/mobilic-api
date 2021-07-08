from app import mailer, app
from app.domain.work_days import compute_aggregate_durations
from app.helpers.errors import MailjetError
from app.models.activity import activity_versions_at
from app.helpers.authentication import current_user


def _max_or_none(*args):
    args_not_none = [a for a in args if a is not None]
    return max(args_not_none) if args_not_none else None


def warn_if_mission_changes_since_latest_user_action(mission, user):
    latest_validation_time = mission.latest_validation_time_for(user)
    all_user_activities = mission.activities_for(
        user, include_dismissed_activities=True
    )
    if not all_user_activities:
        return False
    latest_user_activity_modification_time = max(
        [a.latest_modification_time_by(user) for a in all_user_activities]
    )
    latest_user_action_time = _max_or_none(
        latest_validation_time, latest_user_activity_modification_time
    )

    if not latest_user_action_time:
        # Mission was most likely created by the admin, user is not yet informed of it
        activities = [a for a in all_user_activities if not a.is_dismissed]
        if not activities:
            return False

        start_time, end_time, timers = compute_aggregate_durations(activities)
        try:
            mailer.send_information_email_about_new_mission(
                user=user,
                mission=mission,
                admin=current_user,
                start_time=start_time,
                end_time=end_time,
                timers=timers,
            )
        except MailjetError as e:
            app.logger.exception(e)
        return True

    # User is already informed of the mission
    if any(
        [
            activity.last_update_time > latest_user_action_time
            for activity in all_user_activities
        ]
    ):
        (
            old_start_time,
            old_end_time,
            old_timers,
        ) = compute_aggregate_durations(
            activity_versions_at(all_user_activities, latest_user_action_time)
        )
        (
            new_start_time,
            new_end_time,
            new_timers,
        ) = compute_aggregate_durations(
            [a for a in all_user_activities if not a.is_dismissed]
        )
        if (
            old_start_time != new_start_time
            or old_end_time != new_end_time
            or old_timers["total_work"] != new_timers["total_work"]
        ):
            try:
                mailer.send_warning_email_about_mission_changes(
                    user=user,
                    mission=mission,
                    admin=current_user,
                    old_start_time=old_start_time,
                    new_start_time=new_start_time,
                    old_end_time=old_end_time,
                    new_end_time=new_end_time,
                    old_timers=old_timers,
                    new_timers=new_timers,
                )
            except MailjetError as e:
                app.logger.exception(e)
            return True

    return False
