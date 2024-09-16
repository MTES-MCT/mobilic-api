from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert, User, RegulationCheck
from app.models.regulation_check import UnitType
from app.seed.helpers import get_datetime_tz
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestDifferentPeriods(RegulationsTest):
    def test_bug_logging_beginning_of_week_overrides_weekly_breach(self):
        # This will create a weekly rule breach
        self._log_and_validate_mission(
            mission_name="Weekly breach",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 8, 28, 1, 0),  # mercredi
                    get_datetime_tz(2024, 8, 31, 11, 30),  # samedi
                ],
            ],
        )

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.unit == UnitType.WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)

        # This should not cancel the weekly alert previously found
        self._log_and_validate_mission(
            mission_name="Another mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 8, 25, 23, 0),  # dimanche
                    get_datetime_tz(2024, 8, 26, 1, 0),  # lundi
                ],
            ],
        )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.unit == UnitType.WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
