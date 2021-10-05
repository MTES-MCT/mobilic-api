from datetime import datetime
from flask.ctx import AppContext

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_activity
from app.helpers.errors import (
    OverlappingActivitiesError,
    OverlappingMissionsError,
    InvalidParamsError,
    EmptyActivityDurationError,
)
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.tests import (
    BaseTest,
    UserFactory,
    CompanyFactory,
    AuthenticatedUserContext,
)
from app.tests.helpers import test_db_changes, DBEntryUpdate


class TestActivityOverlaps(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.current_user = UserFactory.create(
            first_name="Tim", last_name="Leader", post__company=self.company
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

    def _log_activity_and_check(
        self, mission, start_time, end_time=None, should_raise=None
    ):
        expected_changes = []
        if not should_raise:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=ActivityType.WORK,
                        start_time=start_time,
                        end_time=end_time,
                        user_id=self.current_user.id,
                        mission_id=mission.id,
                        submitter_id=self.current_user.id,
                    ),
                )
            )

        def action():
            with test_db_changes(expected_changes, watch_models=[Activity]):
                with atomic_transaction(commit_at_end=True):
                    return log_activity(
                        submitter=self.current_user,
                        user=self.current_user,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=False,
                        reception_time=datetime.now(),
                        start_time=start_time,
                        end_time=end_time,
                    )

        if should_raise:
            with self.assertRaises(should_raise):
                action()
        else:
            action()

    def create_mission_with_work_activity(
        self, start_time, end_time=None, should_raise=None
    ):
        mission = Mission.create(
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.current_user,
        )
        self._log_activity_and_check(
            mission=mission,
            start_time=start_time,
            end_time=end_time,
            should_raise=should_raise,
        )
        return mission

    def test_simple_activity_overlap(self):
        mission = self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 8), datetime(2021, 1, 1, 12)
        )
        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 10),
            should_raise=OverlappingActivitiesError,
        )
        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 10),
            datetime(2021, 1, 1, 10, 15),
            should_raise=OverlappingActivitiesError,
        )
        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 7),
            datetime(2021, 1, 1, 8, 15),
            should_raise=OverlappingActivitiesError,
        )
        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 11, 45),
            datetime(2021, 1, 1, 12, 15),
            should_raise=OverlappingActivitiesError,
        )

        self._log_activity_and_check(
            mission, datetime(2021, 1, 1, 12), datetime(2021, 1, 1, 12, 15)
        )

    def test_should_not_log_zero_duration_activities(self):
        mission = self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 8), datetime(2021, 1, 1, 12)
        )

        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 10),
            datetime(2021, 1, 1, 10),
            should_raise=EmptyActivityDurationError,
        )

        self._log_activity_and_check(
            mission,
            datetime(2021, 1, 1, 13),
            datetime(2021, 1, 1, 13),
            should_raise=EmptyActivityDurationError,
        )

    def test_missions_overlap(self):
        mission = self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 8), datetime(2021, 1, 1, 12)
        )
        self._log_activity_and_check(
            mission, datetime(2021, 1, 1, 14), datetime(2021, 1, 1, 18)
        )

        self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 13),
            datetime(2021, 1, 1, 13, 30),
            should_raise=OverlappingMissionsError,
        )
        self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 17),
            datetime(2021, 1, 1, 19),
            should_raise=OverlappingActivitiesError,
        )

        mission_before = self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 6), datetime(2021, 1, 1, 8)
        )
        self._log_activity_and_check(
            mission_before,
            datetime(2021, 1, 1, 13),
            datetime(2021, 1, 1, 13, 30),
            should_raise=OverlappingMissionsError,
        )
        self._log_activity_and_check(
            mission_before,
            datetime(2021, 1, 1, 19),
            datetime(2021, 1, 1, 20, 30),
            should_raise=OverlappingMissionsError,
        )

        self.create_mission_with_work_activity(
            datetime(2021, 1, 1, 18), datetime(2021, 1, 1, 20)
        )
        self._log_activity_and_check(
            mission_before,
            datetime(2021, 1, 1, 21),
            datetime(2021, 1, 1, 22),
            should_raise=OverlappingMissionsError,
        )
