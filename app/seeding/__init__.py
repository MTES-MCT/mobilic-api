import sys

from app import app
from app.seeding.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
)
from config import MOBILIC_ENV


@app.cli.command(with_appcontext=True)
def seed():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)

    print("------ SEEDING DATA -------")

    nb_companies = 10
    nb_employees = 10

    print(f"Creating {nb_companies} companies...")
    companies = [
        CompanyFactory.create(
            usual_name=f"Busy Corp {i + 1}", siren=f"000000{i}"
        )
        for i in range(nb_companies)
    ]
    print(f"{nb_companies} companies created.")

    print(f"Creating admin...")
    admin = UserFactory.create(
        email="busy.admin@test.com",
        password="password",
        first_name="Busy",
        last_name="Admin",
    )
    print(f"Admin created.")

    print(f"Creating {nb_employees} employees per companies.")
    for idx_company, company in enumerate(companies):
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )
        for i in range(nb_employees):
            employee = UserFactory.create(
                email=f"busy.employee{i}@busycorp{idx_company}.com",
                password="password",
                first_name="Employee {i}",
                last_name=f"Corp {idx_company}",
            )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )
        sys.stdout.write(f"\r{idx_company + 1} / {nb_companies}")
    sys.stdout.flush()
    print(f"\nAll done.")
