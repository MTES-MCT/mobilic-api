from app import app
from app.tests import run_tests_from_cli
from app.seed import clean as seed_clean
from app.seed import seed as seed_seed


@app.cli.command(with_appcontext=False)
def test():
    """Run tests."""
    run_tests_from_cli()


@app.cli.command(with_appcontext=True)
def clean():
    """Remove all data from database."""
    seed_clean()


@app.cli.command(with_appcontext=True)
def seed():
    """Inject tests data in database."""
    seed_seed()


@app.cli.command(with_appcontext=True)
def toto():
    """Say Hello."""
    print("Hello toto")
