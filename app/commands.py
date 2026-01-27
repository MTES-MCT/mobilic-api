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
from app.domain.company import job_update_ceased_activity_status
from app.domain.regulations import compute_regulation_for_user
from app.domain.vehicle import find_vehicle
from app.helpers.oauth.models import ThirdPartyApiKey
from app.helpers.xml.greco import temp_write_greco_xml
from app.jobs.auto_validations import job_process_auto_validations
from app.models.company import Company
from app.models.controller_control import ControllerControl
from app.models.user import User
from app.seed import clean as seed_clean, exit_if_prod
from app.seed import seed as seed_seed
from app.jobs.emails.certificate import (
    send_about_to_lose_certificate_emails,
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

    if MOBILIC_ENV == "prod":
        send_certificate_compute_end_notification()


@app.cli.command("send_daily_emails", with_appcontext=True)
def send_daily_emails():
    from datetime import date

    from app.jobs.emails.bizdev import (
        send_onboarding_emails,
        send_companies_without_any_employee_invitation_emails,
        send_companies_with_employees_but_without_activities_emails,
        send_companies_without_activity_reminder_emails,
        send_reminder_no_invitation_emails,
        send_invitation_emails,
        send_companies_with_pending_invitation_emails,
    )

    send_onboarding_emails(date.today())
    send_companies_without_any_employee_invitation_emails(date.today())
    send_companies_with_employees_but_without_activities_emails(date.today())
    send_companies_without_activity_reminder_emails(date.today())
    send_reminder_no_invitation_emails(date.today())
    send_invitation_emails(date.today())
    send_companies_with_pending_invitation_emails(date.today())

    from app.jobs.emails.cgu import (
        send_expiry_warning_email,
        send_email_to_last_company_suspended_admins,
    )

    send_expiry_warning_email()
    send_email_to_last_company_suspended_admins(datetime.datetime.now())

    from app.jobs.emails.send_anonymization_warnings import (
        send_anonymization_warnings,
    )

    send_anonymization_warnings()


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


@app.cli.command("update_ceased_activity_status", with_appcontext=True)
def update_ceased_activity_status():
    job_update_ceased_activity_status()


@app.cli.command("process_auto_validations", with_appcontext=True)
def process_auto_validations():
    job_process_auto_validations()


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

    In test mode, all database changes are rolled back at the end

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


@app.cli.command("sync_brevo_funnel", with_appcontext=True)
@click.option(
    "--acquisition-pipeline",
    default="Acquisition V2",
    help="Brevo pipeline name for acquisition funnel",
)
@click.option(
    "--activation-pipeline",
    default="Activation",
    help="Brevo pipeline name for activation funnel",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose mode for detailed output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be synced without making changes",
)
@click.option(
    "--test-classification",
    is_flag=True,
    help="Test funnel classification logic only",
)
@click.option(
    "--acquisition-only",
    is_flag=True,
    help="Sync only acquisition funnel data",
)
@click.option(
    "--activation-only",
    is_flag=True,
    help="Sync only activation funnel data",
)
def sync_brevo_funnel_command(
    acquisition_pipeline,
    activation_pipeline,
    verbose,
    dry_run,
    test_classification,
    acquisition_only,
    activation_only,
):
    """
    Unified sync of acquisition and activation funnels with Brevo dual pipelines.

    This command syncs companies to two separate Brevo pipelines based on their funnel stage:

    ACQUISITION PIPELINE - Focus on employee account activation:
    - Entreprise inscrite sans compte activé
    - Entreprise inscrite sans compte activé relancée par mail J+2 (TODO - ticket Trello)
    - Entreprise gagnée (at least 1 active employee)
    - Entreprise perdue (no activation after 14 days)

    ACTIVATION PIPELINE - Focus on employee onboarding and platform usage:
    - Entreprise ayant invité moins de 30% de leurs salariés + 0 mission validée
    - Entreprise ayant invité entre 30 et 80% de leurs salariés + 0 mission validée
    - Entreprise ayant invité entre 80 et 100% de leurs salariés + 0 mission validée
    - Entreprise ayant invité 100% de leurs salariés + au moins 1 mission validée par le gestionnaire

    Examples:
    flask sync_brevo_funnel --test-classification
    flask sync_brevo_funnel --dry-run --verbose
    flask sync_brevo_funnel --acquisition-only
    flask sync_brevo_funnel --acquisition-pipeline "Acquisition" --activation-pipeline "Activation" --verbose
    """
    if MOBILIC_ENV == "staging":
        app.logger.info("Brevo sync skipped in staging environment")
        return

    from app.services.brevo import sync_all_funnels
    from app.services.brevo.testing import FunnelTester
    from app.helpers.brevo import brevo

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)

    if acquisition_only and activation_only:
        click.echo(
            "Error: --acquisition-only and --activation-only cannot be used together"
        )
        return

    if test_classification:
        return FunnelTester.run_classification_test(
            acquisition_only, activation_only
        )

    import time
    from app.helpers.mattermost import send_brevo_sync_notification

    start_time = time.time()
    result = None

    try:
        app.logger.info("Starting Brevo sync:")
        app.logger.info(f"  - Acquisition pipeline: {acquisition_pipeline}")
        app.logger.info(f"  - Activation pipeline: {activation_pipeline}")
        app.logger.info(f"  - Dry run: {dry_run}")

        single_funnel_mode = acquisition_only or activation_only
        if single_funnel_mode:
            from app.services.brevo import (
                AcquisitionDataFinder,
                ActivationDataFinder,
                sync_dual_pipeline_funnel,
            )

            acquisition_data, activation_data = [], []

            if acquisition_only:
                activation_data = ActivationDataFinder().find_companies()
                activation_company_ids = [
                    c["company_id"] for c in activation_data
                ]
                acquisition_data = AcquisitionDataFinder().find_companies(
                    exclude_company_ids=activation_company_ids
                )
                app.logger.info(
                    f"  - Acquisition only: {len(acquisition_data)} companies (excluding {len(activation_company_ids)} in activation)"
                )
                activation_data = []

            if activation_only:
                activation_data = ActivationDataFinder().find_companies()
                app.logger.info(
                    f"  - Activation only: {len(activation_data)} companies"
                )

            result = sync_dual_pipeline_funnel(
                acquisition_data=acquisition_data,
                activation_data=activation_data,
                brevo_client=brevo,
                acquisition_pipeline=acquisition_pipeline,
                activation_pipeline=activation_pipeline,
                dry_run=dry_run,
            )
        else:
            result = sync_all_funnels(
                brevo_client=brevo,
                acquisition_pipeline=acquisition_pipeline,
                activation_pipeline=activation_pipeline,
                dry_run=dry_run,
            )

        duration = time.time() - start_time
        mode = "DRY RUN" if dry_run else "SYNC"
        click.echo(f"\n🎯 {mode} RESULTS:")
        click.echo(f"   Total companies: {result.total_companies}")
        click.echo(f"   Created deals: {result.created_deals}")
        click.echo(f"   Updated deals: {result.updated_deals}")
        click.echo(f"   Acquisition synced: {result.acquisition_synced}")
        click.echo(f"   Activation synced: {result.activation_synced}")
        click.echo(f"   Duration: {duration:.1f}s")

        if result.errors:
            click.echo(f"   Errors: {len(result.errors)}")
            for error in result.errors[:3]:
                click.echo(f"     - {error}")
            if len(result.errors) > 3:
                click.echo(
                    f"     ... and {len(result.errors) - 3} more errors"
                )

        app.logger.info(
            f"Brevo sync completed: "
            f"Acquisition {result.acquisition_synced}, "
            f"Activation {result.activation_synced}, "
            f"Total {result.created_deals} created, {result.updated_deals} updated "
            f"in {duration:.1f}s"
        )

        if not dry_run:
            try:
                send_brevo_sync_notification(
                    sync_result=result,
                    duration_seconds=duration,
                    acquisition_pipeline=acquisition_pipeline,
                    activation_pipeline=activation_pipeline,
                )
            except Exception as notify_error:
                app.logger.warning(
                    f"Mattermost notification failed: {notify_error}"
                )

    except Exception as e:
        duration = time.time() - start_time if start_time else None
        error_msg = f"❌ Sync failed: {e}"
        print(error_msg)
        app.logger.error(error_msg)

        if result is None:
            from app.services.brevo.orchestrator import SyncResult

            result = SyncResult(total_companies=0, errors=[str(e)])
        else:
            result.errors.append(f"Sync failed: {str(e)}")

        if not dry_run:
            try:
                send_brevo_sync_notification(
                    sync_result=result,
                    duration_seconds=duration,
                    acquisition_pipeline=acquisition_pipeline,
                    activation_pipeline=activation_pipeline,
                )
            except Exception as notify_error:
                app.logger.error(
                    f"❌ Failed to send failure notification: {notify_error}"
                )

        if verbose:
            import traceback

            traceback.print_exc()
        raise


@app.cli.command(
    "send_anonymization_warnings_or_preview", with_appcontext=True
)
@click.option(
    "--preview",
    is_flag=True,
    help="Preview mode: show statistics without sending emails",
)
def send_anonymization_warnings_or_preview_command(preview):
    """
    Send anonymization warning emails to users scheduled for deletion.

    This command identifies users who will be anonymized in 15 days from the
    configured cutoff date and sends them warning emails.

    Examples:
    flask send_anonymization_warnings --preview
    flask send_anonymization_warnings
    """
    from app.jobs.emails.send_anonymization_warnings import (
        send_anonymization_warnings,
        get_anonymization_warning_preview,
    )

    try:
        if preview:
            app.logger.info("Running in preview mode")
            stats = get_anonymization_warning_preview()

            click.echo("📊 ANONYMIZATION WARNINGS PREVIEW:")
            click.echo(f"   Target anonymization date: {stats['target_date']}")
            click.echo(
                f"   Total inactive employees: {stats['total_inactive_employees']}"
            )
            click.echo(
                f"   Total inactive managers: {stats['total_inactive_managers']}"
            )
            click.echo(f"   Employees to warn: {stats['employees_to_warn']}")
            click.echo(f"   Managers to warn: {stats['managers_to_warn']}")
            click.echo(
                f"   Employees already warned: {stats['employees_already_warned']}"
            )
            click.echo(
                f"   Managers already warned: {stats['managers_already_warned']}"
            )
        else:
            app.logger.info("Sending anonymization warnings")
            results = send_anonymization_warnings()

            click.echo("✉️ ANONYMIZATION WARNINGS SENT:")
            click.echo(f"   Employees: {results['employees_sent']} sent")
            click.echo(f"   Managers: {results['managers_sent']} sent")
            click.echo(f"   Total: {results['total_sent']} sent")

    except Exception as e:
        error_msg = f"❌ Anonymization warnings failed: {e}"
        click.echo(error_msg)
        app.logger.error(error_msg)
        raise


@app.cli.command("link_brevo_deals", with_appcontext=True)
@click.option(
    "--acquisition-pipeline",
    default="Acquisition",
    help="Brevo pipeline name for acquisition funnel",
)
@click.option(
    "--activation-pipeline",
    default="Activation",
    help="Brevo pipeline name for activation funnel",
)
@click.option(
    "--companies-per-page",
    default=1000,
    type=int,
    help="Number of companies to process per page",
)
def link_brevo_deals_command(
    acquisition_pipeline, activation_pipeline, companies_per_page
):
    """Link unlinked deals to existing companies in Brevo using pagination."""
    import time
    from app.helpers.brevo import brevo
    from app.helpers.mattermost import (
        send_brevo_deals_linking_notification,
        DealsLinkingResult,
    )

    start_time = time.time()
    try:
        app.logger.info("Starting deal linking process")

        acquisition_pipeline_id = brevo.get_pipeline_id_by_name(
            acquisition_pipeline
        )
        activation_pipeline_id = brevo.get_pipeline_id_by_name(
            activation_pipeline
        )

        total_linked = 0
        total_errors = 0
        acquisition_linked = 0
        acquisition_errors = 0
        activation_linked = 0
        activation_errors = 0

        if acquisition_pipeline_id:
            print(f"🔗 Linking deals in {acquisition_pipeline} pipeline...")
            result = brevo.link_unlinked_deals_paginated(
                acquisition_pipeline_id, companies_per_page
            )
            acquisition_linked = result["linked"]
            acquisition_errors = result["errors"]
            total_linked += acquisition_linked
            total_errors += acquisition_errors
            print(
                f"   Acquisition: {result['linked']} linked, {result['errors']} errors"
            )

        if activation_pipeline_id:
            print(f"🔗 Linking deals in {activation_pipeline} pipeline...")
            result = brevo.link_unlinked_deals_paginated(
                activation_pipeline_id, companies_per_page
            )
            activation_linked = result["linked"]
            activation_errors = result["errors"]
            total_linked += activation_linked
            total_errors += activation_errors
            print(
                f"   Activation: {result['linked']} linked, {result['errors']} errors"
            )

        duration = time.time() - start_time
        print("LINKING RESULTS:")
        print(f"   Total linked: {total_linked}")
        print(f"   Total errors: {total_errors}")
        print(f"   Duration: {duration:.1f}s")

        app.logger.info(
            f"Deal linking completed: {total_linked} linked, {total_errors} errors in {duration:.1f}s"
        )

        try:
            linking_result = DealsLinkingResult(
                total_linked=total_linked,
                total_errors=total_errors,
                acquisition_linked=acquisition_linked,
                acquisition_errors=acquisition_errors,
                activation_linked=activation_linked,
                activation_errors=activation_errors,
                duration_seconds=duration,
            )
            send_brevo_deals_linking_notification(
                linking_result=linking_result,
                acquisition_pipeline=acquisition_pipeline,
                activation_pipeline=activation_pipeline,
            )
        except Exception as notify_error:
            app.logger.warning(
                f"Mattermost notification failed: {notify_error}"
            )

    except Exception as e:
        duration = time.time() - start_time if start_time else None
        error_msg = f"❌ Linking failed: {e}"
        print(error_msg)
        app.logger.error(error_msg)

        try:
            linking_result = DealsLinkingResult(
                total_linked=0,
                total_errors=1,
                acquisition_linked=0,
                acquisition_errors=0,
                activation_linked=0,
                activation_errors=0,
                duration_seconds=duration,
            )
            send_brevo_deals_linking_notification(
                linking_result=linking_result,
                acquisition_pipeline=acquisition_pipeline,
                activation_pipeline=activation_pipeline,
            )
        except Exception as notify_error:
            app.logger.error(
                f"Failed to send failure notification: {notify_error}"
            )

        raise


@app.cli.command("delete_old_notifications", with_appcontext=True)
def delete_old_notifications():
    """Delete notifications older than 1 month."""
    from datetime import timedelta
    from app.models.notification import Notification
    from app import db

    threshold_date = date.today() - timedelta(days=30)
    try:
        deleted = Notification.query.filter(
            Notification.creation_time < threshold_date
        ).delete(synchronize_session=False)
        db.session.commit()
        print(f"Deleted {deleted} notifications older than 1 month.")
    except Exception as e:
        db.session.rollback()
        print(f"Error while deleting notifications: {e}")
