from datetime import datetime

from app.models import RegulatoryAlert, User
from app.models.activity import ActivityType
from app.seed.helpers import get_date, get_time
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestMisc(RegulationsTest):
    def test_should_ignore_holidays(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Formation de 10h",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=8, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=18, minute=0
                    ),
                    ActivityType.OFF,
                ],
            ],
        )
        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL)
        ).all()
        self.assertEqual(len(regulatory_alerts), 0)
