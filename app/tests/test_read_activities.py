from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.models.queries import query_activities
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.seeding import UserFactory, CompanyFactory
from app.tests.helpers import test_db_changes, DBEntryUpdate


class TestReadActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.workers = [
            UserFactory.create(post__company=self.company) for i in range(0, 2)
        ]
        with app.app_context():
            for day in range(1, 30):
                for user in self.workers:
                    with AuthenticatedUserContext(user=user):
                        mission = Mission.create(
                            submitter=user,
                            company=self.company,
                            reception_time=datetime.now(),
                        )
                        for hour in [8, 10, 12, 14, 16]:
                            activity = log_activity(
                                submitter=user,
                                user=user,
                                mission=mission,
                                type=ActivityType.WORK,
                                switch_mode=True,
                                reception_time=datetime.now(),
                                start_time=datetime(2021, 1, day, hour),
                                end_time=datetime(2021, 1, day, hour + 1, 30),
                            )
                            if hour == 12:
                                activity.dismiss()
        db.session.commit()

    def tearDown(self):
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
                        reception_time=datetime.now(),
                        start_time=start_time,
                        end_time=end_time,
                    )

        if should_raise:
            with self.assertRaises(should_raise):
                action()
        else:
            action()

    def test_simple_read_activities(self):
        user1 = self.workers[0]
        activities = query_activities(user_id=user1.id).all()
        self.assertEqual(len(activities), 29 * 4)

    def test_read_activities_with_time_boundaries(self):
        user1 = self.workers[0]
        activities = query_activities(
            user_id=user1.id, start_time=datetime(2021, 1, 2)
        ).all()
        self.assertEqual(len(activities), 28 * 4)

        activities = query_activities(
            user_id=user1.id, end_time=datetime(2021, 1, 29)
        ).all()
        self.assertEqual(len(activities), 28 * 4)

        activities = query_activities(
            user_id=user1.id,
            start_time=datetime(2021, 1, 2),
            end_time=datetime(2021, 1, 29),
        ).all()
        self.assertEqual(len(activities), 27 * 4)

        activities = query_activities(
            user_id=user1.id,
            start_time=datetime(2021, 1, 2, 9),
            end_time=datetime(2021, 1, 28, 16),
        ).all()
        self.assertEqual(len(activities), 27 * 4)
