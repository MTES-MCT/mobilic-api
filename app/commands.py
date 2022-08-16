import os
import sys
from unittest import TestLoader, TextTestRunner

from config import TestConfig

from app import app
from app.domain.regulations import compute_regulations
from app.helpers.submitter_type import SubmitterType
from app.models.mission_validation import MissionValidation
from app.seed import clean as seed_clean
from app.seed import seed as seed_seed


@app.cli.command(with_appcontext=False)
def test():
    app.config.from_object(TestConfig)
    root_project_path = os.path.dirname(app.root_path)
    test_suite = TestLoader().discover(
        os.path.join(app.root_path, "tests"),
        pattern="test_*.py",
        top_level_dir=root_project_path,
    )
    result = TextTestRunner(verbosity=3).run(test_suite)
    if result.wasSuccessful():
        sys.exit(0)
    sys.exit(1)


@app.cli.command(with_appcontext=True)
def clean():
    """Remove all data from database."""
    seed_clean()


@app.cli.command(with_appcontext=True)
def seed():
    """Inject tests data in database."""
    seed_seed()


@app.cli.command("init_regulation_alerts", with_appcontext=True)
def init_regulation_alerts():
    """Initialize alerts for all validated missions"""
    validated_missions = MissionValidation.query.all()
    for validated_mission in validated_missions:
        mission_activities = validated_mission.mission.acknowledged_activities
        if mission_activities:
            mission_start = mission_activities[0].start_time.date()
            mission_end = (
                mission_activities[-1].end_time.date()
                if mission_activities[-1].end_time
                else None
            )
            submitter_type = (
                SubmitterType.ADMIN
                if validated_mission.is_admin
                else SubmitterType.EMPLOYEE
            )
            users = set([a.user for a in mission_activities])
            for u in users:
                compute_regulations(
                    u, mission_start, mission_end, submitter_type
                )
