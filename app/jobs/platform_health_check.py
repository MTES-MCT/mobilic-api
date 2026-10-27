import time
from datetime import date, datetime, timedelta

import requests
from flask_jwt_extended import create_access_token

from app import app, db
from app.helpers.tchap import send_tchap_message
from app.jobs import log_execution
from app.models import (
    Activity,
    ActivityVersion,
    Comment,
    Expenditure,
    LocationEntry,
    Mission,
    MissionAutoValidation,
    MissionEnd,
    MissionValidation,
    RegulationComputation,
    User,
)

REQUEST_TIMEOUT_SECONDS = 20
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 20
BOT_MISSION_NAME = "[bot] health check"
BOT_USER_EMAIL = "bot-healthcheck@mobilic.beta.gouv.fr"
EXPECTED_EMPLOYEES = 2


class BotCheckError(Exception):
    pass


class BotClient:
    """Calls the API over real HTTP (API_HOST) as the healthcheck bot user."""

    def __init__(self, user_id):
        self.base_url = app.config["API_HOST"].rstrip("/")
        token = create_access_token(
            {"id": user_id, "client_id": None},
            expires_delta=timedelta(minutes=15),
        )
        self.headers = {"Authorization": "Bearer " + token}

    def post(self, path, payload):
        response = requests.post(
            self.base_url + path,
            json=payload,
            headers=self.headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code not in (200, 202):
            raise BotCheckError(
                f"POST {path} returned HTTP {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    def graphql(self, query, variables):
        body = self.post("/graphql", {"query": query, "variables": variables})
        if body.get("errors"):
            message = body["errors"][0].get("message")
            raise BotCheckError(f"GraphQL error: {message}")
        return body["data"]


CREATE_MISSION = """
mutation ($companyId: Int!, $name: String) {
  activities { createMission(companyId: $companyId, name: $name) { id } }
}
"""

LOG_ACTIVITY = """
mutation ($type: ActivityTypeEnum!, $startTime: TimeStamp!, $missionId: Int!) {
  activities { logActivity(type: $type, startTime: $startTime, missionId: $missionId) { id } }
}
"""

CANCEL_MISSION = """
mutation ($missionId: Int!, $userId: Int!) {
  activities { cancelMission(missionId: $missionId, userId: $userId) { id } }
}
"""

COMPANY_USERS = """
query ($id: Int!) {
  company(id: $id) { users { id } }
}
"""


def check_activity_logging(client, user_id, company_id):
    mission_id = client.graphql(
        CREATE_MISSION, {"companyId": company_id, "name": BOT_MISSION_NAME}
    )["activities"]["createMission"]["id"]
    try:
        client.graphql(
            LOG_ACTIVITY,
            {
                "type": "work",
                "startTime": int(time.time()) - 60,
                "missionId": mission_id,
            },
        )
    finally:
        client.graphql(
            CANCEL_MISSION, {"missionId": mission_id, "userId": user_id}
        )


def check_manager_employees(client, company_id, expected_employees):
    users = client.graphql(COMPANY_USERS, {"id": company_id})["company"][
        "users"
    ]
    if len(users) < expected_employees:
        raise BotCheckError(
            f"{len(users)} employees returned, at least {expected_employees} expected"
        )


def check_export_employees(client, company_id, expected_employees):
    body = client.post(
        "/companies/validate_export_params",
        {
            "company_ids": [company_id],
            "min_date": (date.today() - timedelta(days=30)).isoformat(),
            "max_date": date.today().isoformat(),
            "detailed": True,
        },
    )
    user_ids = {uid for chunk in body["chunks"] for uid in chunk["user_ids"]}
    if len(user_ids) < expected_employees:
        raise BotCheckError(
            f"{len(user_ids)} employees in the export, at least {expected_employees} expected"
        )


def _run_with_retries(check):
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        if attempt:
            time.sleep(RETRY_DELAY_SECONDS)
        try:
            check()
            return None
        except Exception as e:
            last_error = e
            app.logger.warning(
                f"Healthcheck bot check attempt {attempt + 1}/{RETRY_ATTEMPTS} failed: {e}"
            )
    return last_error


def _send_alert(failures):
    lines = [
        f"🚨 Mobilic — healthcheck en échec ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
    ]
    for label, error in failures:
        lines.append(f"- {label} : {error}")
    room_id = app.config.get("TCHAP_PLATFORM_ALERTS_ROOM_ID")
    if not send_tchap_message("\n".join(lines), room_id=room_id):
        raise RuntimeError("Healthcheck alert could not be delivered on Tchap")


@log_execution
def job_run_platform_health_checks():
    bot_user = User.query.filter(User.email == BOT_USER_EMAIL).one_or_none()
    company_ids = (
        bot_user.current_company_ids_with_admin_rights if bot_user else []
    )
    if not company_ids:
        _send_alert(
            [
                (
                    "Bot de healthcheck mal configuré",
                    f"compte {BOT_USER_EMAIL} introuvable ou sans entreprise gérée",
                )
            ]
        )
        return

    if not app.config.get("API_HOST"):
        _send_alert(
            [
                (
                    "Bot de healthcheck mal configuré",
                    "variable d'environnement API_HOST non définie",
                )
            ]
        )
        return

    user_id, company_id = bot_user.id, company_ids[0]
    expected_employees = EXPECTED_EMPLOYEES
    client = BotClient(user_id)
    checks = [
        (
            "Enregistrement du temps de travail impossible",
            lambda: check_activity_logging(client, user_id, company_id),
        ),
        (
            "Les salariés ne s'affichent plus pour le gestionnaire",
            lambda: check_manager_employees(
                client, company_id, expected_employees
            ),
        ),
        (
            "Les salariés n'apparaissent plus dans les exports",
            lambda: check_export_employees(
                client, company_id, expected_employees
            ),
        ),
    ]

    failures = []
    for label, check in checks:
        error = _run_with_retries(check)
        if error:
            failures.append((label, error))

    if failures:
        _send_alert(failures)
    app.logger.info(
        f"Healthcheck bot done: {len(checks) - len(failures)}/{len(checks)} ok"
    )


@log_execution
def job_purge_healthcheck_bot_missions(max_age_hours=24):
    """Hard-deletes the missions created by the healthcheck bot and their data."""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    mission_ids = (
        db.session.query(Mission.id)
        .filter(
            Mission.name == BOT_MISSION_NAME,
            Mission.reception_time < cutoff,
        )
        .subquery()
    )
    activity_ids = (
        db.session.query(Activity.id)
        .filter(Activity.mission_id.in_(mission_ids))
        .subquery()
    )
    ActivityVersion.query.filter(
        ActivityVersion.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    for model in (
        Activity,
        Comment,
        Expenditure,
        LocationEntry,
        MissionAutoValidation,
        MissionEnd,
        MissionValidation,
    ):
        model.query.filter(model.mission_id.in_(mission_ids)).delete(
            synchronize_session=False
        )
    deleted = Mission.query.filter(Mission.id.in_(mission_ids)).delete(
        synchronize_session=False
    )
    # Not linked to a mission: the bot user only has bot data.
    RegulationComputation.query.filter(
        RegulationComputation.user_id.in_(
            db.session.query(User.id).filter(User.email == BOT_USER_EMAIL)
        ),
        RegulationComputation.creation_time < cutoff,
    ).delete(synchronize_session=False)
    db.session.commit()
    app.logger.info(f"Purged {deleted} bot missions")
    return deleted
