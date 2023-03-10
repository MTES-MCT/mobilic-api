import os
import secrets
import sys
from datetime import datetime
from unittest import TestLoader, TextTestRunner
from tqdm import tqdm
import psutil

import click
from argon2 import PasswordHasher

from app.helpers.oauth.models import ThirdPartyApiKey
from config import TestConfig

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.regulations import compute_regulation_for_user
from app.models.user import User
from app.seed import clean as seed_clean
from app.seed import seed as seed_seed
from multiprocessing import Pool


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
@click.argument("nb_fork", type=click.INT)
def init_regulation_alerts(part, nb_parts, nb_fork):
    """
    Initialize alerts for users from part PART

    NB_PARTS is a number between 1 and 24
    PART is a number between 1 and NB_PARTS.
    nb_fork is the number of parallel thread can be run.
    It is used to split all users in [NB_PARTS] parts using modulo on user_id.
    """

    if nb_parts < 1 or nb_parts > 24:
        click.echo("ERROR: [nb_parts] should be between 1 and 24")
        sys.exit(1)

    if part < 1 or part > nb_parts:
        click.echo(f"ERROR: [part] should be between 1 and {nb_parts}")
        sys.exit(1)

    print(f"Computing regulation alerts ({part}/{nb_parts})")
    # users_ids = (
    #     db.session.query(User.id).filter(User.id == 247167328).all()
    # )
    users_ids = (
        db.session.query(User.id).filter(User.id % nb_parts == part - 1).all()
    )
    max_value = len(users_ids) if users_ids else 0
    # users = User.query.filter(User.id % nb_parts == part - 1).all()
    # max_value = len(users) if users else 0
    print(f"{max_value} users to process")

    virtual_memory = psutil.virtual_memory()
    total_in_mb = int(virtual_memory.total / (1024 * 1024))
    db.session.close()
    db.engine.dispose()
    # with tqdm(total=max_value, desc="user%", position=3) as usersbar, tqdm(
    #     total=100, desc="-cpu%", position=2
    # ) as cpubar, tqdm(
    #     total=total_in_mb, desc="-ram#", position=1
    # ) as rambar_abs, tqdm(
    #     total=100, desc="-ram%", position=0
    # ) as rambar_perc:
    with Pool(nb_fork) as p:
        p.map(run_batch_user_id, users_ids)
        # for user in users:
        #     with atomic_transaction(commit_at_end=True):
        #         compute_regulation_for_user(user)
        # rambar_abs.n = int(psutil.virtual_memory().used / (1024 * 1024))
        # rambar_perc.n = psutil.virtual_memory().percent
        # cpubar.n = psutil.cpu_percent()
        # usersbar.n += 1
        # rambar_abs.refresh()
        # rambar_perc.refresh()
        # cpubar.refresh()
        # usersbar.refresh()


def run_batch_user_id(user_id):
    with atomic_transaction(commit_at_end=True):
        print(f"**********************************************")
        print(f"{datetime.now()} - COMPUTE BEGINS FOR USER {user_id}")
        user_to_process = User.query.filter(User.id == user_id).one()
        compute_regulation_for_user(user_to_process)
        print(f"{datetime.now()} - COMPUTE FINISHED FOR USER {user_id}")


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
