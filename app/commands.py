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
from app.domain.company import update_ceased_activity_status
from app.domain.regulations import compute_regulation_for_user
from app.domain.vehicle import find_vehicle
from app.helpers.oauth.models import ThirdPartyApiKey
from app.helpers.xml.greco import temp_write_greco_xml
from app.models.company import Company
from app.models.controller_control import ControllerControl
from app.models.user import User
from app.seed import clean as seed_clean, exit_if_prod
from app.seed import seed as seed_seed
from app.jobs.emails.certificate import (
    send_about_to_lose_certificate_emails,
    send_active_then_inactive_companies_emails,
)
from app.services.send_certificate_compute_end_notification import (
    send_certificate_compute_end_notification,
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


@app.cli.command("load_missions", with_appcontext=True)
@click.argument("company_id", required=True)
@click.argument("nb_employees", type=click.INT, required=True)
@click.argument("nb_days", type=click.INT, required=True)
def load_missions(company_id, nb_employees, nb_days):
    exit_if_prod()

    from app.seed.scenarios import load_missions

    company = Company.query.get(company_id)
    admins = company.get_admins(date.today(), None)

    if len(admins) == 0:
        print(f"No admin in company {company_id}")
        sys.exit(0)

    load_missions.run(company, admins[0], nb_employees, nb_days, 1)


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
        send_about_to_lose_certificate_emails(today)
        send_active_then_inactive_companies_emails(today)

    if MOBILIC_ENV == "prod":
        send_certificate_compute_end_notification()


@app.cli.command("send_daily_emails", with_appcontext=True)
def send_daily_emails():
    from datetime import date

    from app.jobs.emails.bizdev import (
        send_onboarding_emails,
        send_companies_without_any_employee_invitation_emails,
        send_companies_with_employees_but_without_activities_emails,
        send_reminder_no_invitation_emails,
        send_invitation_emails,
    )

    send_onboarding_emails(date.today())
    send_companies_without_any_employee_invitation_emails(date.today())
    send_companies_with_employees_but_without_activities_emails(date.today())
    send_reminder_no_invitation_emails(date.today())
    send_invitation_emails(date.today())

    from app.jobs.emails.cgu import (
        send_expiry_warning_email,
        send_email_to_last_company_suspended_admins,
    )

    send_expiry_warning_email()
    send_email_to_last_company_suspended_admins(datetime.datetime.now())


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


@app.cli.command("sync_brevo", with_appcontext=True)
@click.argument("pipeline_names", nargs=-1)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose mode for more detailed output",
)
def sync_brevo_command(pipeline_names, verbose):
    """
    Command to sync companies between the database and Brevo.
    You can specify one or more pipeline names as arguments.
    """
    from app.services.sync_companies_with_brevo import (
        sync_companies_with_brevo,
    )
    from app.helpers.brevo import BrevoApiClient

    if not pipeline_names:
        print("Please provide at least one pipeline name.")
        return

    brevo = BrevoApiClient(app.config["BREVO_API_KEY"])

    app.logger.info(
        f"Process sync companies with Brevo began for pipelines: {pipeline_names}"
    )

    sync_companies_with_brevo(brevo, list(pipeline_names), verbose=verbose)

    app.logger.info("Process sync companies with Brevo done")


@app.cli.command("update_ceased_activity_status", with_appcontext=True)
def _update_ceased_activity_status():
    update_ceased_activity_status()


@app.cli.command("migrate_anonymize_data", with_appcontext=True)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose mode for more detailed output",
)
@click.option(
    "--no-dry-run",
    is_flag=True,
    help="Disable dry run mode: anonymize data AND delete original records",
)
@click.option(
    "--delete-only",
    is_flag=True,
    help="Delete-only mode: only delete original data that has already been anonymized",
)
@click.option(
    "--test",
    is_flag=True,
    help="Test mode: rollback all changes at the end",
)
@click.option(
    "--force-clean",
    is_flag=True,
    help="Delete the content of IdMapping table",
)
def anonymize_standalone_data_command(
    verbose, no_dry_run, delete_only, test, force_clean
):
    """
    Migrate data older than threshold to anonymized tables.

    This command operates by default in dry run mode, which only anonymizes data
    without deleting original records.

    Available modes:
    - Dry run mode (default): Only anonymize data without deleting originals
    - Normal mode (--no-dry-run): Anonymize and delete data in one operation
    - Delete-only mode (--delete-only): Delete original data that has already been anonymized

    In test mode, all database changes are rolled back at the end.
    """
    from app.services.anonymization import anonymize_expired_data

    if no_dry_run and delete_only:
        click.echo(
            "Error: --no-dry-run and --delete-only cannot be used together"
        )
        return

    dry_run = not no_dry_run

    anonymize_expired_data(
        verbose=verbose,
        dry_run=dry_run,
        delete_only=delete_only,
        test_mode=test,
        force_clean=force_clean,
    )


@app.cli.command("anonymize_users", with_appcontext=True)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose mode for more detailed output",
)
@click.option(
    "--no-dry-run",
    is_flag=True,
    help="Disable dry run mode: perform actual anonymization",
)
@click.option(
    "--test",
    is_flag=True,
    help="Test mode: rollback all changes at the end",
)
@click.option(
    "--force-clean",
    is_flag=True,
    help="Delete the content of IdMapping table",
)
def anonymize_users_command(verbose, no_dry_run, test, force_clean):
    """
    Anonymize users older than threshold.

    This command operates by default in dry run mode, which creates ID mappings
    without modifying user records.

    Available modes:
    - Dry run mode (default): Create ID mappings without modifying users
    - Normal mode (--no-dry-run): Perform actual anonymization with user modifications

    In test mode, all database changes are rolled back at the end.

    Recommended workflow:
    1. Run with default settings to create ID mappings
    2. Run with --no-dry-run to perform actual anonymization
    """
    from app.services.anonymization.user_related import anonymize_users

    dry_run = not no_dry_run

    anonymize_users(
        verbose=verbose,
        dry_run=dry_run,
        test_mode=test,
        force_clean=force_clean,
    )
