import sys

from app import app, db
from app.models import User, Employment, Company, RefreshToken
from app.seeding.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
)
from config import MOBILIC_ENV

NB_COMPANIES = 10
NB_EMPLOYEES = 10


def exit_if_prod():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)


@app.cli.command(with_appcontext=True)
def clean():
    exit_if_prod()

    print("------ CLEANING DATA -------")
    Employment.query.delete()
    Company.query.delete()
    RefreshToken.query.delete()
    User.query.delete()
    db.session.commit()


@app.cli.command(with_appcontext=True)
def seed():
    exit_if_prod()

    print("------ SEEDING DATA -------")

    print(f"Creating {NB_COMPANIES} companies...")
    companies = [
        CompanyFactory.create(
            usual_name=f"Busy Corp {i + 1}", siren=f"000000{i}"
        )
        for i in range(NB_COMPANIES)
    ]
    print(f"{NB_COMPANIES} companies created.")

    print(f"Creating admin...")
    admin = UserFactory.create(
        email="busy.admin@test.com",
        password="password",
        first_name="Busy",
        last_name="Admin",
    )
    print(f"Admin created.")

    print(f"Creating {NB_EMPLOYEES} employees per companies.")
    for idx_company, company in enumerate(companies):
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )
        for i in range(NB_EMPLOYEES):
            employee = UserFactory.create(
                email=f"busy.employee{i}@busycorp{idx_company}.com",
                password="password",
                first_name=f"Employee {i}",
                last_name=f"Corp {idx_company}",
            )
            EmploymentFactory.create(
                company=company,
                submitter=admin,
                user=employee,
                has_admin_rights=False,
            )
        sys.stdout.write(f"\r{idx_company + 1} / {NB_COMPANIES}")
    sys.stdout.flush()
    print(f"\nAll done.")
