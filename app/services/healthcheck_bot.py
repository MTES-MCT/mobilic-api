from datetime import date, datetime

from sqlalchemy import text

from app import app, db
from app.jobs.platform_health_check import BOT_USER_EMAIL
from app.models import Company, Employment, User
from app.models.employment import EmploymentRequestValidationStatus

BOT_COMPANY_NAME = "[Bot] Entreprise de test healthcheck"
MAX_BOT_EMPLOYEES = 50
BOT_EMPLOYEE_EMAIL_PATTERN = "bot-healthcheck-salarie-{n}@mobilic.beta.gouv.fr"

MISSION_CHILD_TABLES = (
    "activity_version",
    "activity",
    "comment",
    "expenditure",
    "location_entry",
    "mission_auto_validation",
    "mission_end",
    "mission_validation",
)
USER_TABLES = (
    "regulation_computation",
    "regulatory_alert",
    "notification",
    "refresh_token",
    "export",
    "email",
    "user_agreement",
    "push_subscription",
    "user_read_token",
    "user_survey_actions",
    "oauth2_authorization_code",
    "oauth2_token",
    "team_admin_user",
)
COMPANY_TABLES = (
    "team",
    "vehicle",
    "company_known_address",
    "company_stats",
    "company_certification",
    "third_party_client_company",
)


def _employee_emails(nb_employees):
    return [
        BOT_EMPLOYEE_EMAIL_PATTERN.format(n=n)
        for n in range(1, nb_employees + 1)
    ]


def _get_or_create_user(email, first_name, last_name):
    user = User.query.filter(User.email == email).one_or_none()
    if user:
        return user, False
    # No password: nobody can log in with this account
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        has_activated_email=True,
        has_confirmed_email=True,
    )
    db.session.add(user)
    db.session.flush()
    return user, True


def _ensure_employment(company, user, submitter, is_admin):
    existing = Employment.query.filter(
        Employment.company_id == company.id,
        Employment.user_id == user.id,
        ~Employment.is_dismissed,
    ).first()
    if existing:
        return False
    db.session.add(
        Employment(
            company=company,
            user=user,
            submitter=submitter,
            reception_time=datetime.now(),
            start_date=date(2000, 1, 1),
            validation_status=EmploymentRequestValidationStatus.APPROVED,
            validation_time=datetime.now(),
            has_admin_rights=is_admin,
        )
    )
    return True


def create_healthcheck_bot(nb_employees=2):
    """Idempotent: creates the healthcheck bot (user, company, employees) if missing, leaves existing data untouched."""
    bot, _ = _get_or_create_user(BOT_USER_EMAIL, "Bot", "Healthcheck")

    company = Company.query.filter(
        Company.usual_name == BOT_COMPANY_NAME
    ).one_or_none()
    if not company:
        company = Company(
            usual_name=BOT_COMPANY_NAME,
            siren_api_info_last_update=date.today(),
        )
        db.session.add(company)
        db.session.flush()

    _ensure_employment(company, bot, bot, is_admin=True)
    for n, email in enumerate(_employee_emails(nb_employees), start=1):
        employee, _ = _get_or_create_user(email, "Salarié", f"Bot {n}")
        _ensure_employment(company, employee, bot, is_admin=False)

    db.session.commit()
    return bot, company


def _delete(table, column, ids):
    if not ids:
        return
    db.session.execute(
        text(f'DELETE FROM "{table}" WHERE {column} = ANY(:ids)'),
        {"ids": list(ids)},
    )


def delete_healthcheck_bot():
    """
    Removes the bot company, its users and all their data. Refuses to run
    if the company has members that are not bot accounts. Everything is
    done in one transaction: any remaining foreign key makes it roll back.
    """
    company = Company.query.filter(
        Company.usual_name == BOT_COMPANY_NAME
    ).one_or_none()
    bot = User.query.filter(User.email == BOT_USER_EMAIL).one_or_none()

    user_ids = set()
    if company:
        members = (
            User.query.join(Employment, Employment.user_id == User.id)
            .filter(Employment.company_id == company.id)
            .all()
        )
        allowed = {BOT_USER_EMAIL, *_employee_emails(MAX_BOT_EMPLOYEES)}
        foreign = [m.email for m in members if m.email not in allowed]
        if foreign:
            raise RuntimeError(
                f"Refusing to delete: company has non-bot members {foreign}"
            )
        user_ids |= {m.id for m in members}
    if bot:
        user_ids.add(bot.id)
    user_ids |= {
        u.id
        for u in User.query.filter(
            User.email.in_(_employee_emails(MAX_BOT_EMPLOYEES))
        ).all()
    }
    if not company and not user_ids:
        return False

    try:
        if company:
            mission_ids = [
                row[0]
                for row in db.session.execute(
                    text("SELECT id FROM mission WHERE company_id = :c"),
                    {"c": company.id},
                )
            ]
            activity_ids = [
                row[0]
                for row in db.session.execute(
                    text("SELECT id FROM activity WHERE mission_id = ANY(:m)"),
                    {"m": mission_ids},
                )
            ]
            _delete("activity_version", "activity_id", activity_ids)
            for table in MISSION_CHILD_TABLES[1:]:
                _delete(table, "mission_id", mission_ids)
            _delete("mission", "id", mission_ids)
            _delete("team_admin_user", "user_id", user_ids)
            _delete("employment", "company_id", [company.id])
            for table in COMPANY_TABLES:
                _delete(table, "company_id", [company.id])
            _delete("company", "id", [company.id])
        for table in USER_TABLES:
            _delete(table, "user_id", user_ids)
        _delete("user", "id", user_ids)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    app.logger.info("Healthcheck bot deleted")
    return True
