import os
import sys
from unittest import TestLoader, TextTestRunner

import progressbar
from config import TestConfig

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.regulations import compute_regulation_for_mission
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
    widgets = [progressbar.Percentage(), progressbar.Bar()]
    validated_missions = MissionValidation.query.all()
    max_value = len(validated_missions) if validated_missions else 0
    bar = progressbar.ProgressBar(widgets=widgets, max_value=max_value).start()
    i = 0
    for validated_mission in validated_missions:
        with atomic_transaction(commit_at_end=True):
            compute_regulation_for_mission(validated_mission)
        i += 1
        bar.update(i)
    bar.finish()
