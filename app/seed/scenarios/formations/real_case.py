import datetime
import json
import os

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import User, Employment
from app.models.activity import ActivityType
from app.seed.helpers import AuthenticatedUserContext, create_mission
from app.seed.scenarios.formations import _clean_recent_data

REAL_CASES_DIR = os.path.join(os.path.dirname(__file__), "real_cases")


def _normalize_activities(acts):
    """Real prod data sometimes has open-ended or duplicate-start activities
    (driver forgot to close, team-mode overlaps...). The exclusion constraint
    `no_overlapping_acknowledged_activities` rejects those on replay, so we
    dedupe by start (prefer closed) and close open ones at the next start."""
    acts = sorted(acts, key=lambda a: a["start"])
    by_start = {}
    for a in acts:
        existing = by_start.get(a["start"])
        if existing is None or (existing.get("end") is None and a.get("end")):
            by_start[a["start"]] = a
    acts = sorted(by_start.values(), key=lambda a: a["start"])
    for i in range(len(acts) - 1):
        if acts[i].get("end") is None:
            acts[i]["end"] = acts[i + 1]["start"]
    if acts and acts[-1].get("end") is None:
        acts = acts[:-1]
    return acts


def run_scenario_formation_real_case(employee_email, control_id):
    """
    Replays a real field-control case onto a sandbox account.
    Loads activity history from real_cases/formation_real_case_<id>.json,
    shifts dates so the case ends yesterday, then recreates missions and
    activities under `employee_email`, with employee + admin validation.

    ponytail: only mission name + activities (type/start/end) are replayed,
    skipped: versions, expenditures, location_entries, comments. Add them
    when trainers ask to see edit history or expenditure reporting.
    """
    employee = User.query.filter(User.email == employee_email).one_or_none()
    if not employee:
        return

    path = os.path.join(
        REAL_CASES_DIR, f"formation_real_case_{control_id}.json"
    )
    with open(path) as f:
        data = json.load(f)

    _clean_recent_data(employee)

    company = employee.employments[0].company
    admin_employment = Employment.query.filter(
        Employment.has_admin_rights == True,
        Employment.company_id == company.id,
        Employment.user_id.isnot(None),
    ).first()
    if not admin_employment:
        print(f"WARN: no admin user for company {company.id}, skipping")
        return
    admin = admin_employment.user

    history_end = datetime.date.fromisoformat(data["history_end"])
    shift = datetime.date.today() - history_end - datetime.timedelta(days=1)

    def parse(ts):
        return datetime.datetime.fromisoformat(ts) + shift

    for m in data["missions"]:
        acts = _normalize_activities(m["activities"])
        if not acts:
            continue
        first_start = parse(acts[0]["start"])
        mission = create_mission(
            name=m["name"] or "Mission",
            company=company,
            time=first_start,
            submitter=employee,
        )
        db.session.commit()

        with AuthenticatedUserContext(user=employee):
            for a in acts:
                start = parse(a["start"])
                end = parse(a["end"]) if a.get("end") else None
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=mission,
                    type=ActivityType(a["type"]),
                    switch_mode=False,
                    reception_time=end or start,
                    start_time=start,
                    end_time=end,
                )
            db.session.commit()
            validate_mission(
                submitter=employee,
                mission=mission,
                for_user=employee,
            )

        with AuthenticatedUserContext(user=admin):
            validate_mission(
                submitter=admin,
                mission=mission,
                for_user=employee,
            )
        db.session.commit()


if __name__ == "__main__":
    # ponytail self-check: shift maps history_end onto yesterday
    history_end = datetime.date.fromisoformat("2026-04-29")
    shift = datetime.date.today() - history_end - datetime.timedelta(days=1)
    moved = datetime.datetime.fromisoformat("2026-04-29T18:00:00") + shift
    assert moved.date() == datetime.date.today() - datetime.timedelta(days=1)

    # ponytail self-check: normalization closes open activities and
    # dedupes duplicate-start activities
    out = _normalize_activities(
        [
            {"type": "drive", "start": "2026-04-01T08:00", "end": None},
            {
                "type": "work",
                "start": "2026-04-01T10:00",
                "end": "2026-04-01T11:00",
            },
            {"type": "drive", "start": "2026-04-01T10:00", "end": None},
            {"type": "drive", "start": "2026-04-01T12:00", "end": None},
        ]
    )
    assert [a["end"] for a in out] == [
        "2026-04-01T10:00",
        "2026-04-01T11:00",
    ], out
    print("OK")
