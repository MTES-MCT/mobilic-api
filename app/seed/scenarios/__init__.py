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
from app.seed.scenarios.two_weeks import (
    ADMIN_EMAIL as ADMIN_TWO_WEEKS,
    EMPLOYEE_EMAIL as EMPLOYEE_TWO_WEEKS,
)
from app.seed.scenarios.controls import run_scenario_controls
from app.seed.scenarios.temps_de_liaison import run_scenario_temps_de_liaison
from app.seed.scenarios.two_weeks import run_scenario_non_stop


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
    SeedScenario(
        "Rules breachers",
        f"Creates a company where everybody break rules !",
        [BREACH_EMPLOYEE_EMAIL],
        run_scenario_breach_rules,
    ),
    SeedScenario(
        "Non Stop",
        "Creates a mission non stop for two weeks",
        [ADMIN_TWO_WEEKS, EMPLOYEE_TWO_WEEKS],
        run_scenario_non_stop,
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
        "Controls",
        "Creates one controller user",
        [],
        run_scenario_controls,
    ),
]
