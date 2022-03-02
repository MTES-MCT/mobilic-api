from dataclasses import dataclass
from typing import Callable, List

from app.seed.scenarios.busy_admin import (
    NB_COMPANIES,
    NB_EMPLOYEES,
    ADMIN_USER_NAME,
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
from app.seed.scenarios.temps_de_liaison import run_scenario_temps_de_liaison


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
    # SeedScenario(
    #     "Busy Admin",
    #     f"Creates an admin managing {NB_COMPANIES} companies with {NB_EMPLOYEES} employees each, logging some time in missions",
    #     [ADMIN_USER_NAME],
    #     run_scenario_busy_admin,
    # ),
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
]
