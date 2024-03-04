from app import mailer, app
from app.helpers.errors import (
    LogActivityInHolidayMissionError,
    LogHolidayInNotEmptyMissionError,
)
from app.helpers.mail import MailjetError
from app.domain.permissions import company_admin


def check_if_mission_holiday(mission):
    if mission.is_holiday():
        raise LogActivityInHolidayMissionError()


def check_log_holiday_only_in_empty_mission(mission):
    if not mission.is_empty():
        raise LogHolidayInNotEmptyMissionError


def send_email_log_holiday(admin, user, company, title, periods):
    if len(periods) == 0:
        return

    is_submitter_admin = company_admin(admin, company.id)
    if not (is_submitter_admin and admin.id != user.id):
        return

    try:
        mailer.send_worker_holiday_logging_notification(
            admin=admin,
            user=user,
            company=company,
            title=title,
            periods=periods,
        )
    except MailjetError as e:
        app.logger.exception(e)
