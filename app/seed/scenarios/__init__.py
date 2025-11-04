from dataclasses import dataclass
from typing import Callable, List

from app.seed.scenarios.breach_rules import (
    run_scenario_breach_rules,
    EMPLOYEE_EMAIL as BREACH_EMPLOYEE_EMAIL,
)
from app.seed.scenarios.busy_admin import (
    NB_COMPANIES,
    NB_EMPLOYEES,
    ADMIN_EMAIL,
    run_scenario_busy_admin,
)
from app.seed.scenarios.certificated_company import run_scenario_certificated
from app.seed.scenarios.lot_of_missions import run_scenario_lot_of_missions
from app.seed.scenarios.multi_businesses import run_scenario_multi_businesses
from app.seed.scenarios.run_certificate import scenario_run_certificate
from app.seed.scenarios.temps_de_liaison import (
    ADMIN_EMAIL as ADMIN_TEMPS_DE_LIAISON,
    EMPLOYEE_EMAIL as EMPLOYEE_TEMPS_DE_LIAISON,
)
from app.seed.scenarios.invitations import (
    ADMIN_EMAIL as ADMIN_INVITATIONS,
    EMPLOYEE_EMAIL as EMPLOYEE_INVITATIONS,
    run_scenario_invitations,
)
from app.seed.scenarios.export_excel import (
    ADMIN_EMAIL as ADMIN_EXPORT,
    run_scenario_export_excel,
)
from app.seed.scenarios.certificated_company import (
    ADMIN_EMAIL as CERTIFICATED_ADMIN_EMAIL,
    EMPLOYEE_EMAIL as CERTIFICATED_EMPLOYEE_EMAIL,
)
from app.seed.scenarios.controls import run_scenario_controls
from app.seed.scenarios.temps_de_liaison import run_scenario_temps_de_liaison
from app.seed.scenarios.third_party import (
    ADMIN_EMAIL as ADMIN_THIRD_PARTY,
    EMPLOYEE_CONFIRMED_EMAIL,
    EMPLOYEE_DISMISSED_EMAIL,
    EMPLOYEE_INVITED_EMAIL,
    EMPLOYEE_NOT_INVITED_EMAIL,
    run_scenario_third_party,
)
from app.seed.scenarios.team_mode import (
    SUPER_ADMIN_EMAIL,
    run_scenario_team_mode,
)
from app.seed.scenarios.multi_businesses import (
    ADMIN_EMAIL as MULTI_ADMIN_EMAIL,
    EMPLOYEE_EMAIL as MULTI_EMPLOYEE_EMAIL,
)


@dataclass
class SeedScenario:
    title: str
    description: str
    user_names: List[str]
    run_func: Callable

    def run(self):
        print("\n------------------------------")
        print(f"Running Scenario: {self.title}")
        print("\nDescription")
        print(f"{self.description}")
        print(f"\nUser names: {' / '.join(self.user_names)}")
        self.run_func()
        print("------------------------------")


scenarios = [
    SeedScenario("Test de charge", "", [], run_scenario_lot_of_missions),
    SeedScenario(
        "Rules breachers",
        f"Creates a company where everybody break rules !",
        [BREACH_EMPLOYEE_EMAIL],
        run_scenario_breach_rules,
    ),
    SeedScenario(
        "Certificated company",
        "Creates a company which should be compliant enough to get a Mobilic certificate",
        [CERTIFICATED_ADMIN_EMAIL, CERTIFICATED_EMPLOYEE_EMAIL],
        run_scenario_certificated,
    ),
    SeedScenario(
        "Busy Admin",
        f"Creates an admin managing {NB_COMPANIES} companies with {NB_EMPLOYEES} employees each, logging some time in missions",
        [ADMIN_EMAIL],
        run_scenario_busy_admin,
    ),
    SeedScenario(
        "Temps de Liaison",
        f"Creates an admin managing a company with one employee",
        [ADMIN_TEMPS_DE_LIAISON, EMPLOYEE_TEMPS_DE_LIAISON],
        run_scenario_temps_de_liaison,
    ),
    SeedScenario(
        "Invitations",
        "Creates one admin, one employee with no job",
        [ADMIN_INVITATIONS, EMPLOYEE_INVITATIONS],
        run_scenario_invitations,
    ),
    SeedScenario(
        "Export Excel Admin",
        "Creates one admin, two companies, to test excel export",
        [ADMIN_EXPORT],
        run_scenario_export_excel,
    ),
    SeedScenario(
        "Third party",
        "Creates one company with client and 4 employees",
        [
            ADMIN_THIRD_PARTY,
            EMPLOYEE_NOT_INVITED_EMAIL,
            EMPLOYEE_INVITED_EMAIL,
            EMPLOYEE_DISMISSED_EMAIL,
            EMPLOYEE_CONFIRMED_EMAIL,
        ],
        run_scenario_third_party,
    ),
    SeedScenario(
        "Team mode",
        "Creates one company with one team",
        [
            SUPER_ADMIN_EMAIL,
            "team.admin{i}@test.com",
            "team.employee{i}@test.com",
        ],
        run_scenario_team_mode,
    ),
    SeedScenario(
        "Multi businesses",
        "Crée une entreprise et un salarié avec des alertes portant sur plusieurs types d'activité différentes",
        [MULTI_ADMIN_EMAIL, MULTI_EMPLOYEE_EMAIL],
        run_scenario_multi_businesses,
    ),
    SeedScenario(
        "Controls",
        "Creates one controller user",
        [],
        run_scenario_controls,
    ),
    SeedScenario(
        "Certificate computation",
        "Run certificate computation",
        [],
        scenario_run_certificate,
    ),
]
