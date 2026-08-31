from datetime import datetime

from app import db
from app.models.activity import ActivityType
from app.models.activity_version import ActivityVersion
from app.seed import UserFactory, CompanyFactory
from app.seed.helpers import get_time
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
    init_regulation_checks_data,
    init_businesses_data,
)


class TestActivityContextValidation(BaseTest):
    """
    The context free field must be a JSON object : third-party clients
    sending a plain string used to corrupt activity versions and break
    manager validation (Trello card 2762).
    """

    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()
        self.company = CompanyFactory.create()
        self.worker = UserFactory.create(post__company=self.company)
        create_mission_response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.create_mission,
            variables={"company_id": self.company.id},
        )
        self.mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]

    def _log_activity(self, context):
        return make_authenticated_request(
            time=get_time(how_many_days_ago=1, hour=15),
            submitter_id=self.worker.id,
            query=ApiRequests.log_activity,
            variables=dict(
                type=ActivityType.WORK,
                start_time=get_time(how_many_days_ago=1, hour=14),
                end_time=get_time(how_many_days_ago=1, hour=15),
                mission_id=self.mission_id,
                switch=False,
                context=context,
            ),
        )

    def test_log_activity_rejects_string_context(self):
        response = self._log_activity(context="a plain string")

        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )

    def test_log_activity_accepts_object_context(self):
        response = self._log_activity(context={"userComment": "ok"})

        self.assertNotIn("errors", response)
        self.assertIsNotNone(
            response["data"]["activities"]["logActivity"]["id"]
        )

    def test_validate_mission_survives_legacy_string_context(self):
        # Simulate an activity stored before the boundary check, whose
        # context is a bare string: validateMission used to crash with
        # "'str' object has no attribute 'get'" (issue #779).
        activity_id = self._log_activity(context={"userComment": "ok"})[
            "data"
        ]["activities"]["logActivity"]["id"]
        version = ActivityVersion.query.filter(
            ActivityVersion.activity_id == activity_id
        ).one()
        version.context = "a plain string"
        db.session.commit()

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                mission_id=self.mission_id, users_ids=[self.worker.id]
            ),
        )

        self.assertNotIn("errors", response)
        self.assertIsNotNone(
            response["data"]["activities"]["validateMission"]["id"]
        )

    def test_edit_activity_rejects_string_context(self):
        activity_id = self._log_activity(context=None)["data"]["activities"][
            "logActivity"
        ]["id"]

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=1, hour=16),
            submitter_id=self.worker.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=activity_id,
                end_time=get_time(how_many_days_ago=1, hour=16),
                context="a plain string",
            ),
        )

        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )
