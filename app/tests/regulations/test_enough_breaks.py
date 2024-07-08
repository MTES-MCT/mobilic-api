from app.domain.mission import had_user_enough_break_last_mission
from app.seed.helpers import get_time
from app.tests.regulations import RegulationsTest


class TestEnoughBreaks(RegulationsTest):
    def test_no_mission_ok(self):
        # No mission, no warning
        self.assertTrue(had_user_enough_break_last_mission(self.employee))

    def test_one_mission_not_enough_break_ko(self):
        how_many_days_ago = 4

        # If a user logs one mission with not enough break time
        self._log_and_validate_mission(
            mission_name="Not enough breaks",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago, hour=14),
                ],
            ],
        )
        # He has a warning
        self.assertFalse(had_user_enough_break_last_mission(self.employee))

        how_many_days_ago = 2

        # If a user then logs one mission with enough break time
        self._log_and_validate_mission(
            mission_name="Enough breaks",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago, hour=10),
                ],
            ],
        )
        # He no longer has a warning
        self.assertTrue(had_user_enough_break_last_mission(self.employee))
