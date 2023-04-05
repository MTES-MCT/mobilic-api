import datetime
import os
import secrets
import sys
from datetime import date
from unittest import TestLoader, TextTestRunner

import click
import progressbar
from argon2 import PasswordHasher

from app.domain.certificate_criteria import compute_company_certifications
from app.helpers.oauth.models import ThirdPartyApiKey
from config import TestConfig

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.regulations import compute_regulation_for_user
from app.models.user import User
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
@click.argument("part", type=click.INT)
@click.argument("nb_parts", type=click.INT)
def init_regulation_alerts(part, nb_parts):
    """
    Initialize alerts for users from part PART

    NB_PARTS is a number between 1 and 24
    PART is a number between 1 and NB_PARTS.
    It is used to split all users in [NB_PARTS] parts using modulo on user_id.
    """

    if nb_parts < 1 or nb_parts > 24:
        click.echo("ERROR: [nb_parts] should be between 1 and 24")
        sys.exit(1)

    if part < 1 or part > nb_parts:
        click.echo(f"ERROR: [part] should be between 1 and {nb_parts}")
        sys.exit(1)

    print(f"Computing regulation alerts ({part}/{nb_parts})")
    widgets = [progressbar.Percentage(), progressbar.Bar()]
    users = User.query.filter(User.id % nb_parts == part - 1).all()
    max_value = len(users) if users else 0
    print(f"{max_value} users to process")
    bar = progressbar.ProgressBar(widgets=widgets, max_value=max_value).start()
    i = 0
    for user in users:
        with atomic_transaction(commit_at_end=True):
            compute_regulation_for_user(user)
        i += 1
        bar.update(i)
    bar.finish()


@app.cli.command("create_api_key", with_appcontext=True)
@click.argument("client_id", type=click.INT)
def create_api_key(client_id):
    """
    Create an API Key for a given OAuth client

    BEWARE : The outputed API KEY will be encrypted in DB, the one that has to be given the client
    is outputed by this function, and can not be retrieved later.

    """

    token = secrets.token_hex(60)
    print("*****************************************************************")
    print("************* TOKEN TO COMMUNICATE TO THE CLIENT ****************")
    print("*************** DO NOT FORGET TO ADD THE PREFIX *****************")
    print("*****************************************************************")
    print(token)
    print("*****************************************************************")
    print("*****************************************************************")

    ph = PasswordHasher()
    token_hash = ph.hash(token)

    db_model = ThirdPartyApiKey(client_id=client_id, api_key=token_hash)
    db.session.add(db_model)
    db.session.commit()


@app.cli.command("run_certificate", with_appcontext=True)
@click.argument("as_of_date", required=False)
def run_certificate(as_of_date=None):
    """
    Run certificate as of today

    as_of_date is an optional date with format 2023-03-01
    """

    today = (
        datetime.datetime.strptime(as_of_date, "%Y-%m-%d").date()
        if as_of_date is not None
        else date.today()
    )
    compute_company_certifications(today)


@app.cli.command("send_onboarding_emails", with_appcontext=True)
def send_onboarding_emails():
    from app.services.send_onboarding_emails import send_onboarding_emails
    from datetime import date

    app.logger.info("Beginning send_onboarding_emails task")

    send_onboarding_emails(date.today())
    app.logger.info("Ending send_onboarding_emails task")
