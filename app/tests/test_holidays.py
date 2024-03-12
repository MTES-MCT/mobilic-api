from datetime import datetime

from flask.ctx import AppContext

from app import app
from app.domain.log_activities import log_activity
from app.helpers.errors import (
    LogActivityInHolidayMissionError,
    LogHolidayInNotEmptyMissionError,
)
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import UserFactory, CompanyFactory
from app.seed.helpers import get_time
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import ApiRequests, make_authenticated_request


class TestHolidays(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.current_user = UserFactory.create(
            first_name="The", last_name="Employee", post__company=self.company
        )
        self.admin_user = UserFactory.create(
            first_name="The",
            last_name="Manager",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self._app_context = AppContext(app)
        self.current_user_context = AuthenticatedUserContext(
            user=self.current_user
        )
        self._app_context.__enter__()
        self.current_user_context.__enter__()

    def tearDown(self):
        self.current_user_context.__exit__(None, None, None)
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _create_mission(self):
        return Mission.create(
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.current_user,
        )

    def _log_activity(self, mission, activity_type, start_time, end_time):
        return log_activity(
            submitter=self.current_user,
            user=self.current_user,
            mission=mission,
            type=activity_type,
            switch_mode=False,
            reception_time=datetime.now(),
            start_time=start_time,
            end_time=end_time,
        )

    def test_ok_log_holiday_in_new_mission(self):
        mission = self._create_mission()
        activity = self._log_activity(
            mission=mission,
            activity_type=ActivityType.OFF,
            start_time=get_time(2, 7, 0),
            end_time=get_time(2, 16, 0),
        )
        self.assertIsNotNone(activity)

    def test_ko_log_activity_in_holiday_mission(self):
        with self.assertRaises(LogActivityInHolidayMissionError):
            mission = self._create_mission()
            self._log_activity(
                mission=mission,
                activity_type=ActivityType.OFF,
                start_time=get_time(2, 7, 0),
                end_time=get_time(2, 10, 0),
            )
            self._log_activity(
                mission=mission,
                activity_type=ActivityType.WORK,
                start_time=get_time(2, 14, 0),
                end_time=get_time(2, 18, 0),
            )

    def test_ko_log_holiday_in_not_empty_mission(self):
        with self.assertRaises(LogHolidayInNotEmptyMissionError):
            mission = self._create_mission()
            self._log_activity(
                mission=mission,
                activity_type=ActivityType.WORK,
                start_time=get_time(2, 7, 0),
                end_time=get_time(2, 10, 0),
            )
            self._log_activity(
                mission=mission,
                activity_type=ActivityType.OFF,
                start_time=get_time(2, 14, 0),
                end_time=get_time(2, 18, 0),
            )

    def test_cancel_mission_holiday(self):
        mission = self._create_mission()
        activity = self._log_activity(
            mission=mission,
            activity_type=ActivityType.OFF,
            start_time=get_time(2, 7, 0),
            end_time=get_time(2, 16, 0),
        )
        self.assertIsNotNone(activity)

        cancel_mission_response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=mission.id,
                user_id=self.current_user.id,
            ),
        )
        self.assertEqual(
            cancel_mission_response["data"]["activities"]["cancelMission"][
                "activities"
            ][0]["id"],
            activity.id,
        )
        if "errors" in cancel_mission_response:
            self.fail(
                f"Cancel mission returned an error: {cancel_mission_response}"
            )
