import os
import sys
from unittest import TestLoader, TextTestRunner

import progressbar
from app.models.user import User
from config import TestConfig

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.regulations import compute_regulation_for_user
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
    """Initialize alerts for all users"""
    widgets = [progressbar.Percentage(), progressbar.Bar()]
    users = User.query.all()
    max_value = len(users) if users else 0
    bar = progressbar.ProgressBar(widgets=widgets, max_value=max_value).start()
    i = 0
    for user in users:
        with atomic_transaction(commit_at_end=True):
            compute_regulation_for_user(user)
        i += 1
        bar.update(i)
    bar.finish()
