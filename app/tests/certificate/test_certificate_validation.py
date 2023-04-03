from datetime import date, datetime

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    previous_month_period,
    compute_log_in_real_time,
    compute_validate_regularly,
)
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import Mission, MissionEnd, MissionValidation
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    AuthenticatedUserContext,
)
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import ApiRequests


class TestCertificateValidation(BaseTest):
    def setUp(self):
        super().setUp()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        self.start, self.end = previous_month_period(date(2023, 3, 28))

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_company_validation_ko_no_misssion(self):
        self.assertFalse(
            compute_validate_regularly(self.company, self.start, self.end)
        )

    def test_company_validation_ko_one_mission_not_validated(self):
        mission_date = datetime(2023, 2, 12)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 12, 10, 5),
                start_time=datetime(2023, 2, 12, 10),
            )
            db.session.commit()

            db.session.add(
                MissionEnd(
                    submitter=self.worker,
                    reception_time=datetime(2023, 2, 12, 18),
                    user=self.worker,
                    mission=mission,
                )
            )

        self.assertFalse(
            compute_validate_regularly(self.company, self.start, self.end)
        )

    def test_company_validation_ok_one_mission_validated(self):
        mission_date = datetime(2023, 2, 12)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 12, 14),
                end_time=datetime(2023, 2, 12, 13),
                start_time=datetime(2023, 2, 12, 10),
            )
            db.session.commit()

            db.session.add(
                MissionEnd(
                    submitter=self.worker,
                    reception_time=datetime(2023, 2, 12, 18),
                    user=self.worker,
                    mission=mission,
                )
            )
            db.session.commit()

            db.session.add(
                MissionValidation(
                    submitter=self.admin,
                    mission=mission,
                    user=self.worker,
                    reception_time=datetime(2023, 2, 15),
                    is_admin=True,
                    creation_time=datetime(2023, 2, 15),
                )
            )

        self.assertTrue(
            compute_validate_regularly(self.company, self.start, self.end)
        )

    def test_company_validation_ko_one_mission_validated_too_late(self):
        mission_date = datetime(2023, 2, 12)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 12, 14),
                end_time=datetime(2023, 2, 12, 13),
                start_time=datetime(2023, 2, 12, 10),
            )
            db.session.commit()

            db.session.add(
                MissionEnd(
                    submitter=self.worker,
                    reception_time=datetime(2023, 2, 12, 18),
                    user=self.worker,
                    mission=mission,
                )
            )
            db.session.commit()

            db.session.add(
                MissionValidation(
                    submitter=self.admin,
                    mission=mission,
                    user=self.worker,
                    reception_time=datetime(2023, 2, 20),
                    is_admin=True,
                    creation_time=datetime(2023, 2, 20),
                )
            )

        self.assertFalse(
            compute_validate_regularly(self.company, self.start, self.end)
        )
