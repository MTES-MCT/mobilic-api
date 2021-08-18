from app import mailer, app
from app.domain.work_days import compute_aggregate_durations
from app.helpers.mail import MailjetError
from app.models.activity import activity_versions_at
from app.helpers.authentication import current_user
from app.models.mission import UserMissionModificationStatus


def warn_if_mission_changes_since_latest_user_action(mission, user):
    (
        modification_status,
        latest_user_action_time,
    ) = mission.modification_status_and_latest_action_time_for_user(user)
    all_user_activities = mission.activities_for(
        user, include_dismissed_activities=True
    )

    if (
        modification_status
        == UserMissionModificationStatus.ONLY_OTHERS_ACTIONS
    ):
        start_time, end_time, timers = compute_aggregate_durations(
            [a for a in all_user_activities if not a.is_dismissed]
        )
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
    if (
        modification_status
        == UserMissionModificationStatus.OTHERS_MODIFIED_AFTER_USER
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
