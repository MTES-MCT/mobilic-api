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
from app.seed import UserFactory, CompanyFactory
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
        self.first_worker = self.workers[0]
        with app.app_context():
            for user in self.workers:
                with AuthenticatedUserContext(user=user):
                    mission = Mission.create(
                        submitter=user,
                        company=self.company,
                        reception_time=datetime.now(),
                    )
                    activity = log_activity(
                        submitter=user,
                        user=user,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=True,
                        reception_time=datetime.now(),
                        start_time=datetime(2022, 1, 1, 1),
                    )
                    activity.dismiss(dismiss_time=datetime(2022, 1, 1, 0, 59))
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

    def test_simple_read_activities(self):
        activities = query_activities(user_id=self.first_worker.id).all()
        self.assertEqual(len(activities), 29 * 4)

    def test_read_activities_with_time_boundaries(self):
        user1 = self.first_worker
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

    def test_dismissed_activity_with_no_end_time(self):
        activities = query_activities(
            user_id=self.first_worker.id,
            start_time=datetime(2022, 2, 1, 0),
            include_dismissed_activities=True,
        ).all()
        self.assertEqual(0, len(activities))

    def test_dismissed_at_before_start_time(self):
        activities = query_activities(
            user_id=self.first_worker.id,
            start_time=datetime(2022, 1, 1, 0),
            include_dismissed_activities=True,
        ).all()
        self.assertEqual(1, len(activities))
