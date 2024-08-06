import datetime
import os
import secrets
import sys
from datetime import date
from multiprocessing import Pool

import click
from argon2 import PasswordHasher
from sqlalchemy import text

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.certificate_criteria import compute_company_certifications
from app.domain.regulations import compute_regulation_for_user
from app.domain.vehicle import find_vehicle
from app.helpers.oauth.models import ThirdPartyApiKey
from app.helpers.xml.greco import temp_write_greco_xml
from app.models.controller_control import ControllerControl
from app.models.user import User
from app.seed import clean as seed_clean
from app.seed import seed as seed_seed
from app.services.send_about_to_lose_certificate_emails import (
    send_about_to_lose_certificate_emails,
)
from app.services.send_active_then_inactive_companies_emails import (
    send_active_then_inactive_companies_emails,
)
from app.services.send_certificate_compute_end_notification import (
    send_certificate_compute_end_notification,
)
from app.services.send_lost_companies_emails import (
    send_never_active_companies_emails,
)
from config import TestConfig, MOBILIC_ENV


@app.cli.command(with_appcontext=False)
@click.argument("test_names", nargs=-1)
def test(test_names):
    app.config.from_object(TestConfig)

    import unittest

    if test_names:
        """Run specific unit tests.

        Example:
        $ flask test app.tests.test_authentication ...
        """
        test_suite = unittest.TestLoader().loadTestsFromNames(test_names)
    else:
        """Run unit tests"""
        root_project_path = os.path.dirname(app.root_path)
        test_suite = unittest.TestLoader().discover(
            os.path.join(app.root_path, "tests"),
            pattern="test_*.py",
            top_level_dir=root_project_path,
        )
    result = unittest.TextTestRunner(verbosity=3).run(test_suite)
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


def _clean_vehicle():
    sql = text(
        """ select translate(UPPER(v.registration_number), '- ', ''),
                           v.company_id,
                           count(translate(UPPER(v.registration_number), '- ', ''))
                    from vehicle v
                    group by 1, 2
                    having count(translate(UPPER(v.registration_number), '- ', '')) > 1"""
    )
    result = db.engine.execute(sql)
    for duplicate_vehicles_info in result:
        vehicles_to_deduplicate = find_vehicle(
            registration_number=duplicate_vehicles_info[0],
            company_id=duplicate_vehicles_info[1],
        )
        vehicle_to_keep = None
        vehicles_possibly_not_terminated = filter_vehicle(
            vehicles_to_deduplicate, lambda v: not v.is_terminated
        )
        if len(vehicles_possibly_not_terminated) == 1:
            vehicle_to_keep = vehicles_possibly_not_terminated[0]
        else:
            vehicles_possibly_with_alias = filter_vehicle(
                vehicles_possibly_not_terminated, lambda v: v.alias is not None
            )
            if len(vehicles_possibly_with_alias) == 1:
                vehicle_to_keep = vehicles_possibly_with_alias[0]
            else:
                vehicles_possibly_with_kilometer = filter_vehicle(
                    vehicles_possibly_with_alias,
                    lambda v: v.last_kilometer_reading is not None,
                )
                if len(vehicles_possibly_with_kilometer) == 1:
                    vehicle_to_keep = vehicles_possibly_with_kilometer[0]
                else:
                    vehicle_to_keep = max(
                        vehicles_possibly_with_kilometer,
                        key=lambda v: v.creation_time,
                    )
        vehicles_to_delete = list(
            filter(
                lambda v: v.id != vehicle_to_keep.id, vehicles_to_deduplicate
            )
        )
        vehicles_ids_to_delete = [v.id for v in vehicles_to_delete]
        print(f"vehicles_ids_to_delete {vehicles_ids_to_delete}")
        print(f"vehicle_to_keep {vehicle_to_keep.id}")
        for id_to_delete in vehicles_ids_to_delete:
            db.session.execute(
                "UPDATE team_vehicle t SET vehicle_id = :new_id WHERE t.vehicle_id = :id_to_delete AND NOT EXISTS(SELECT 1 from team_vehicle t2 where t2.team_id = t.team_id AND t2.vehicle_id = :new_id)",
                {
                    "new_id": vehicle_to_keep.id,
                    "id_to_delete": id_to_delete,
                },
            )
        db.session.execute(
            "DELETE FROM team_vehicle WHERE vehicle_id IN :old_ids",
            {
                "old_ids": tuple(vehicles_ids_to_delete),
            },
        )
        db.session.execute(
            "UPDATE mission SET vehicle_id = :new_id WHERE company_id = :company_id AND vehicle_id IN :old_ids",
            {
                "company_id": duplicate_vehicles_info[1],
                "new_id": vehicle_to_keep.id,
                "old_ids": tuple(vehicles_ids_to_delete),
            },
        )
        db.session.execute(
            "DELETE FROM VEHICLE WHERE id IN :old_ids AND company_id = :company_id",
            {
                "company_id": duplicate_vehicles_info[1],
                "old_ids": tuple(vehicles_ids_to_delete),
            },
        )
        print(
            f"DELETE VEHICLES {duplicate_vehicles_info[0]} FROM COMPANY {duplicate_vehicles_info[1]}"
        )
        db.session.commit()


@app.cli.command()
def clean_vehicle():
    print(f"Cleaning the duplicate vehicles")
    _clean_vehicle()


def filter_vehicle(list_to_filter, filter_function):
    vehicles_filtered = list(filter(filter_function, list_to_filter))
    if len(vehicles_filtered) == 0:
        return list_to_filter
    else:
        return vehicles_filtered


@app.cli.command("init_regulation_alerts", with_appcontext=True)
@click.argument("part", type=click.INT)
@click.argument("nb_parts", type=click.INT)
@click.argument("nb_fork", type=click.INT)
def init_regulation_alerts(part, nb_parts, nb_fork):
    """
    Initialize alerts for users

    part is a number between 1 and NB_PARTS.
    nb_parts is a number between 1 and 24
    It is used to split all users in [NB_PARTS] parts using modulo on user_id.
    nb_fork is the number of parallel thread can be run.
    """

    if nb_parts < 1 or nb_parts > 24:
        click.echo("ERROR: [nb_parts] should be between 1 and 24")
        sys.exit(1)

    if part < 1 or part > nb_parts:
        click.echo(f"ERROR: [part] should be between 1 and {nb_parts}")
        sys.exit(1)

    print(f"Computing regulation alerts ({part}/{nb_parts})")
    users_ids = (
        db.session.query(User.id).filter(User.id % nb_parts == part - 1).all()
    )
    max_value = len(users_ids) if users_ids else 0
    print(f"{max_value} users to process")

    db.session.close()
    db.engine.dispose()

    with Pool(nb_fork) as p:
        p.map(run_batch_user_id, users_ids)


def run_batch_user_id(user_id):
    with atomic_transaction(commit_at_end=True):
        user_to_process = User.query.filter(User.id == user_id).one()
        compute_regulation_for_user(user_to_process)


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
@click.argument("computation_only", type=click.BOOL, required=False)
def run_certificate(as_of_date=None, computation_only=False):
    """
    Run certificate as of today

    as_of_date is an optional date with format 2023-03-01
    computation_only is an optional boolean

    Example: flask run_certificate 2023-03-01 true
    """

    today = (
        datetime.datetime.strptime(as_of_date, "%Y-%m-%d").date()
        if as_of_date is not None
        else date.today()
    )
    app.logger.info("Process run_certificate began")
    compute_company_certifications(today)
    app.logger.info("Process run_certificate done")

    if not computation_only:
        app.logger.info("Process send_about_to_lose_certificate_emails began")
        send_about_to_lose_certificate_emails(today)
        app.logger.info("Process send_about_to_lose_certificate_emails done")

        app.logger.info(
            "Process send_active_then_inactive_companies_emails began"
        )
        send_active_then_inactive_companies_emails(today)
        app.logger.info(
            "Process send_active_then_inactive_companies_emails done"
        )

    if MOBILIC_ENV == "prod":
        send_certificate_compute_end_notification()


@app.cli.command("send_daily_emails", with_appcontext=True)
def send_daily_emails():
    from app.services.send_onboarding_emails import send_onboarding_emails
    from datetime import date

    app.logger.info("Beginning task send_onboarding_emails")
    send_onboarding_emails(date.today())
    app.logger.info("Ending task send_onboarding_emails")

    app.logger.info("Beginning task send_never_active_companies_emails")
    send_never_active_companies_emails(datetime.datetime.now())
    app.logger.info("Ending task send_never_active_companies_emails")

    from app.services.send_suspended_company_account_due_to_cgu import (
        send_suspended_company_account_due_to_cgu,
    )

    app.logger.info("Beginning task send_suspended_company_account_due_to_cgu")
    send_suspended_company_account_due_to_cgu(datetime.datetime.now())
    app.logger.info("Ending task send_suspended_company_account_due_to_cgu")


@app.cli.command("load_company_stats", with_appcontext=True)
def load_company_stats():
    from app.services.load_company_stats import load_company_stats

    app.logger.info("Process load_company_stats began")
    load_company_stats()
    app.logger.info("Process load_company_stats done")


@app.cli.command("temp_generate_xml", with_appcontext=True)
@click.argument("id", required=True)
def temp_command_generate_xm_control(id):
    control = ControllerControl.query.get(id)
    temp_write_greco_xml(control)
