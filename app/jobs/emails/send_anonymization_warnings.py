from datetime import datetime, timedelta

from app import app, mailer
from app.helpers.mail import MailjetError
from app.jobs import log_execution
from app.services.anonymization.user_related.classifier import UserClassifier
from app.services.anonymization.common import AnonymizationManager
from app.helpers.mail_type import EmailType
from app.domain.email import get_warned_user_ids
from app.domain.user import (
    get_employees_for_anonymization_warning,
    get_managers_with_companies_for_anonymization_warning,
)

WARNING_DAYS_AHEAD = 15
DUPLICATE_PREVENTION_DAYS = 14


@log_execution
def send_anonymization_warnings():
    """
    Send anonymization warning emails to users scheduled for deletion.

    This function identifies users who will be anonymized in 15 days from the
    configured cutoff date and sends them warning emails.
    """
    app.logger.info("Starting anonymization warning email process")

    anonymization_manager = AnonymizationManager("warning")
    base_cutoff_date = anonymization_manager.calculate_cutoff_date()

    # Find users who will become eligible for anonymization in 15 days
    inactivity_cutoff_date = base_cutoff_date + timedelta(
        days=WARNING_DAYS_AHEAD
    )

    # Date shown in email when anonymization will happen
    anonymization_scheduled_date = datetime.now() + timedelta(
        days=WARNING_DAYS_AHEAD
    )

    app.logger.info(
        f"Base cutoff: {base_cutoff_date.date()}, "
        f"Inactivity cutoff: {inactivity_cutoff_date.date()}, "
        f"Anonymization scheduled: {anonymization_scheduled_date.date()}"
    )

    classifier = UserClassifier(inactivity_cutoff_date)
    inactive_data = classifier.find_inactive_users()

    if not inactive_data["users"] and not inactive_data["admins"]:
        app.logger.info("No users found for anonymization warning")
        return {"employees_sent": 0, "managers_sent": 0, "total_sent": 0}

    # Don't re-warn users who received warning email in last 14 days
    duplicate_check_cutoff = datetime.now() - timedelta(
        days=DUPLICATE_PREVENTION_DAYS
    )
    warned_user_ids = get_warned_user_ids(
        [
            EmailType.ANONYMIZATION_WARNING_EMPLOYEE,
            EmailType.ANONYMIZATION_WARNING_MANAGER,
        ],
        duplicate_check_cutoff,
    )

    employees = get_employees_for_anonymization_warning(
        inactive_data["users"], warned_user_ids
    )

    managers = get_managers_with_companies_for_anonymization_warning(
        inactive_data["admins"], warned_user_ids
    )

    app.logger.info(
        f"Found {len(employees)} employees and {len(managers)} managers to warn"
    )

    anonymization_date_str = anonymization_scheduled_date.strftime("%d/%m/%Y")
    employees_sent = _send_employee_warnings(employees, anonymization_date_str)
    managers_sent = _send_manager_warnings(managers, anonymization_date_str)

    total_sent = employees_sent + managers_sent
    app.logger.info(
        f"Anonymization warnings sent: {employees_sent} employees, {managers_sent} managers, {total_sent} total"
    )

    return {
        "employees_sent": employees_sent,
        "managers_sent": managers_sent,
        "total_sent": total_sent,
    }


def _send_employee_warnings(employees, warning_date_str):
    sent = 0
    for employee in employees:
        try:
            mailer.send_anonymization_warning_employee_email(
                employee, warning_date_str
            )
            sent += 1
            app.logger.info(
                f"Sent anonymization warning to employee {employee.id}"
            )
        except MailjetError as e:
            app.logger.error(
                f"Failed to send warning to employee {employee.id}: {e}"
            )
        except Exception as e:
            app.logger.exception(
                f"Unexpected error sending warning to employee {employee.id}: {e}"
            )

    return sent


def _send_manager_warnings(managers, warning_date_str):
    sent = 0
    for manager_data in managers:
        try:
            manager = manager_data["manager"]
            companies = manager_data["companies"]

            for company in companies:
                mailer.send_anonymization_warning_manager_email(
                    manager, company, warning_date_str
                )

            sent += 1
            app.logger.info(
                f"Sent anonymization warning to manager {manager.id}"
            )
        except MailjetError as e:
            app.logger.error(
                f"Failed to send warning to manager {manager.id}: {e}"
            )
        except Exception as e:
            app.logger.exception(
                f"Unexpected error sending warning to manager {manager.id}: {e}"
            )

    return sent


def get_anonymization_warning_preview():
    app.logger.info("Getting anonymization warning preview")

    anonymization_manager = AnonymizationManager("warning")
    base_cutoff_date = anonymization_manager.calculate_cutoff_date()

    # Users inactive before this date will be warned
    classifier_cutoff_date = base_cutoff_date + timedelta(
        days=WARNING_DAYS_AHEAD
    )

    # Date shown in email when anonymization will happen
    anonymization_scheduled_date = datetime.now() + timedelta(
        days=WARNING_DAYS_AHEAD
    )

    classifier = UserClassifier(classifier_cutoff_date)
    inactive_data = classifier.find_inactive_users()

    # Don't re-warn users who received warning email in last 14 days
    duplicate_check_cutoff = datetime.now() - timedelta(
        days=DUPLICATE_PREVENTION_DAYS
    )
    warned_user_ids = get_warned_user_ids(
        [
            EmailType.ANONYMIZATION_WARNING_EMPLOYEE,
            EmailType.ANONYMIZATION_WARNING_MANAGER,
        ],
        duplicate_check_cutoff,
    )

    total_employees = len(inactive_data["users"])
    total_managers = len(inactive_data["admins"])
    employees_already_warned = len(
        [uid for uid in inactive_data["users"] if uid in warned_user_ids]
    )
    managers_already_warned = len(
        [uid for uid in inactive_data["admins"] if uid in warned_user_ids]
    )

    return {
        "target_date": anonymization_scheduled_date.strftime("%d/%m/%Y"),
        "total_inactive_employees": total_employees,
        "total_inactive_managers": total_managers,
        "employees_to_warn": total_employees - employees_already_warned,
        "managers_to_warn": total_managers - managers_already_warned,
        "employees_already_warned": employees_already_warned,
        "managers_already_warned": managers_already_warned,
    }
