from dataclasses import dataclass
from typing import Callable

from app.seed.scenarios.busy_admin import (
    NB_COMPANIES,
    NB_EMPLOYEES,
    ADMIN_USER_NAME,
    run_scenario_busy_admin,
)
from app.seed.scenarios.temps_de_liaison import (
    ADMIN_USER_NAME as ADMIN_TEMPS_DE_LIAISON,
)
from app.seed.scenarios.temps_de_liaison import run_scenario_temps_de_liaison


@dataclass
class SeedScenario:
    title: str
    description: str
    user_name: str
    run_func: Callable

    def run(self):
        print("\n------------------------------")
        print(f"Running Scenario: {self.title}")
        print("\nDescription")
        print(f"{self.description}")
        print(f"\nUser name: {self.user_name}")
        self.run_func()
        print("------------------------------")


scenarios = [
    # SeedScenario(
    #     "Busy Admin",
    #     f"Creates an admin managing {NB_COMPANIES} companies with {NB_EMPLOYEES} employees each, logging some time in missions",
    #     ADMIN_USER_NAME,
    #     run_scenario_busy_admin,
    # ),
    SeedScenario(
        "Temps de Liaison",
        f"Creates an admin managing a company with one employee",
        ADMIN_TEMPS_DE_LIAISON,
        run_scenario_temps_de_liaison,
    )
]
