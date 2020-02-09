from flask_migrate import upgrade
from unittest import TestLoader, TextTestRunner
import os

from app import app, db
from config import TestConfig


@app.cli.command(with_appcontext=False)
def test():
    app.config.from_object(TestConfig)
    with app.app_context():
        db.engine.execute("DROP schema public CASCADE; CREATE schema public;")
        upgrade()
        root_project_path = os.path.dirname(app.root_path)
        test_suite = TestLoader().discover(
            os.path.join(app.root_path, "tests"),
            pattern="test_*.py",
            top_level_dir=root_project_path,
        )
        TextTestRunner(verbosity=2).run(test_suite)
