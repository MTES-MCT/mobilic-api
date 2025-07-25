from datetime import datetime

from app import mailer, app
from app.domain.user import get_employee_current_admins
from app.domain.work_days import compute_aggregate_durations
from app.helpers.mail import MailjetError
from app.helpers.mattermost import send_mattermost_message
from app.models.activity import activity_versions_at
from app.helpers.authentication import current_user
from app.models.mission import UserMissionModificationStatus
from app.models import Company, UserAgreement
from app.helpers.notification_type import NotificationType
from app.helpers.time import to_tz
from app.models.notification import create_notification
from dateutil.tz import gettz


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
            # do not include off service if mission is holiday
            # because this notification is handled in LogHoliday
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
            if not user.is_an_admin:
                user_timezone = gettz(user.timezone_name)
                create_notification(
                    user_id=user.id,
                    notification_type=NotificationType.NEW_MISSION_BY_ADMIN,
                    data={
                        "mission_id": mission.id,
                        "mission_start_date": to_tz(
                            start_time, user_timezone
                        ).isoformat(),
                    },
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
            activity_versions_at(all_user_activities, latest_user_action_time),
            mission.is_holiday(),
        )
        (
            new_start_time,
            new_end_time,
            new_timers,
        ) = compute_aggregate_durations(
            [a for a in all_user_activities if not a.is_dismissed],
            mission.is_holiday(),
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
                    is_holiday=mission.is_holiday(),
                )

                if not user.is_an_admin:
                    user_timezone = gettz(user.timezone_name)
                    create_notification(
                        user_id=user.id,
                        notification_type=NotificationType.MISSION_CHANGES_WARNING,
                        data={
                            "mission_id": mission.id,
                            "mission_start_date": to_tz(
                                old_start_time, user_timezone
                            ).isoformat(),
                        },
                    )
            except MailjetError as e:
                app.logger.exception(e)
            return True

    return False


def send_email_to_admins_when_employee_rejects_cgu(employee):
    try:
        admins = get_employee_current_admins(employee=employee)
        mailer.send_admin_employee_rejects_cgu_email(
            employee=current_user, admins=admins
        )
    except MailjetError as e:
        app.logger.exception(e)


def warn_if_company_has_no_admin_left(company_ids, last_admin, expiry_date):
    today = datetime.now().date()
    companies = Company.query.filter(Company.id.in_(company_ids)).all()
    for company in companies:
        admins = company.get_admins(start=today, end=today)

        has_at_least_one_admin = False
        for admin in admins:
            if not UserAgreement.has_user_rejected(user_id=admin.id):
                has_at_least_one_admin = True
                break

        if has_at_least_one_admin:
            continue

        send_mattermost_message(
            thread_title="Entreprise sans gestionnaire",
            main_title="Une entreprise n'a plus de gestionnaire",
            main_value=f"Le dernier gestionnaire de l'entreprise a refusé les CGUs, son compte sera supprimé le {expiry_date.strftime('%Y-%m-%d')}",
            items=[
                {
                    "title": "Identifiant de l'entreprise",
                    "value": company.id,
                    "short": True,
                },
                {
                    "title": "Nom de l'entreprise",
                    "value": company.usual_name,
                    "short": True,
                },
                {
                    "title": "Email du gestionnaire",
                    "value": last_admin.email,
                    "short": True,
                },
                {
                    "title": "Numéro de téléphone du gestionnaire",
                    "value": last_admin.phone_number
                    if last_admin.phone_number
                    else "-",
                    "short": True,
                },
            ],
        )
