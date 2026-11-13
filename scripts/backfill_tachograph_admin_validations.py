"""One-off backfill (card 2860): admin-validate migrated tachograph missions.

"Activités tachygraphe" periods logged as OFF holidays never got an admin
(auto-)validation: validate_mission skips it for holidays. Migration
4402ca8e8bd4 flipped them to WORK but did not create it, so the manager's
regulatory view (admin-validated missions only) still counts them as rest.

Admin-validate each like the nightly auto-validation job, which also computes
the day's admin regulation. A full recompute is deliberately avoided: it replays
unrelated history and trips the activity-overlap constraint on some users.

Run locally against the target DB through the SSH tunnel:
    pipenv run python scripts/backfill_tachograph_admin_validations.py            # dry-run
    EXECUTE=1 pipenv run python scripts/backfill_tachograph_admin_validations.py  # write
"""

import os
from datetime import datetime

from sqlalchemy import text

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.validation import validate_mission
from app.models import Mission, User

EXECUTE = os.environ.get("EXECUTE") == "1"
MISSION_NAME = "Activités tachygraphe"


def candidates():
    rows = db.session.execute(
        text(
            """
            select distinct m.id as mission_id, a.user_id
            from mission m
            join activity a on a.mission_id = m.id
                           and a.dismissed_at is null and a.type = 'work'
            where m.name = :name
              and not exists (
                  select 1 from mission_auto_validation mav
                  where mav.mission_id = m.id and mav.is_admin is true
              )
            order by m.id, a.user_id
            """
        ),
        {"name": MISSION_NAME},
    ).fetchall()
    pairs = [
        (Mission.query.get(r.mission_id), User.query.get(r.user_id))
        for r in rows
    ]
    return [(m, u) for m, u in pairs if not m.validated_by_admin_for(u)]


def main():
    with app.app_context():
        print(
            "DB:",
            db.session.execute(text("select current_database()")).scalar(),
        )
        pairs = candidates()
        print(f"{len(pairs)} migrated mission(s) without admin validation")
        for mission, user in pairs:
            print(f"  mission {mission.id} user {user.id}")

        if not EXECUTE:
            print("Dry-run. Set EXECUTE=1 to admin-validate.")
            return

        ok, failed = 0, 0
        for mission, user in pairs:
            try:
                with atomic_transaction(commit_at_end=True):
                    validation = validate_mission(
                        mission=mission,
                        submitter=None,
                        for_user=user,
                        creation_time=datetime.now(),
                        is_auto_validation=True,
                        is_admin_validation=True,
                    )
                    db.session.add(validation)
                ok += 1
            except Exception as e:
                db.session.rollback()
                failed += 1
                print(f"  FAILED mission {mission.id} user {user.id}: {e}")
        print(f"Admin-validated {ok} mission(s); {failed} failed.")


if __name__ == "__main__":
    main()
