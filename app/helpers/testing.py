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
        test_suite = TestLoader().discover(
            app.root_path,
            pattern="test_*.py",
            top_level_dir=os.path.dirname(app.root_path),
        )
        print(f"Found {test_suite.countTestCases()} tests to run")
        TextTestRunner().run(test_suite)
