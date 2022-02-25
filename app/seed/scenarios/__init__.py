from dataclasses import dataclass
from typing import Callable

from app.seed.scenarios.busy_admin import (
    NB_COMPANIES,
    NB_EMPLOYEES,
    ADMIN_USER_NAME,
    run_scenario_busy_admin,
)


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
    SeedScenario(
        "Busy Admin",
        f"Creates an admin managing {NB_COMPANIES} companies with {NB_EMPLOYEES} employees each, logging some time in missions",
        ADMIN_USER_NAME,
        run_scenario_busy_admin,
    )
]
