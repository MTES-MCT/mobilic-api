from datetime import datetime, timedelta

from flask.ctx import AppContext

from app import app, db
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import Activity, ActivityType
from app.seed import UserFactory, CompanyFactory
from app.tests import BaseTest, AuthenticatedUserContext
from app.tests.helpers import (
    init_regulation_checks_data,
    init_businesses_data,
    make_authenticated_request,
    ApiRequests,
)


class TestValidateMissionNoFreezeSideEffect(BaseTest):
    """Admin edits between employee and admin validation must survive validateMission without activityItems."""

    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_admin_edit_persists_through_validate_mission(self):
        start_time = datetime(2026, 6, 16, 12, 6)
        end_time = datetime(2026, 6, 16, 12, 7)

        with AuthenticatedUserContext(user=self.admin):
            mission = Mission.create(
                submitter=self.admin,
                company=self.company,
                reception_time=start_time,
            )
            log_activity(
                submitter=self.admin,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=end_time,
                start_time=start_time,
                end_time=end_time,
            )
        db.session.commit()
        activity_id = mission.activities[0].id

        make_authenticated_request(
            time=end_time + timedelta(seconds=1),
            submitter_id=self.worker.id,
            query=ApiRequests.validate_mission,
            variables={
                "missionId": mission.id,
                "usersIds": [self.worker.id],
            },
        )

        new_start_time = datetime(2026, 6, 16, 12, 5)
        make_authenticated_request(
            time=end_time + timedelta(seconds=10),
            submitter_id=self.admin.id,
            query=ApiRequests.edit_activity,
            variables={
                "activityId": activity_id,
                "startTime": int(new_start_time.timestamp()),
                "endTime": int(end_time.timestamp()),
            },
        )

        db.session.expire_all()
        edited_start_time = Activity.query.get(activity_id).start_time

        make_authenticated_request(
            time=end_time + timedelta(seconds=20),
            submitter_id=self.admin.id,
            query=ApiRequests.validate_mission,
            variables={
                "missionId": mission.id,
                "usersIds": [self.worker.id],
            },
        )

        db.session.expire_all()
        activity = Activity.query.get(activity_id)
        assert (
            activity.start_time == edited_start_time
        ), f"reverted: {activity.start_time}"
