from app.seed.helpers import (
    get_datetime_tz,
)
from app.tests.regulations import RegulationsTest


class TestEndOfWeek(RegulationsTest):
    def test_logging_on_last_day_of_week_no_error(self):
        self._log_and_validate_mission(
            mission_name=f"Temps la semaine suivante",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 9, 30, 18),  # lundi
                    get_datetime_tz(2024, 9, 30, 20),
                ],
            ],
        )
        self._log_and_validate_mission(
            mission_name=f"Log fin de semaine",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 9, 29, 18),  # dimanche
                    get_datetime_tz(2024, 9, 29, 20),
                ],
            ],
        )
