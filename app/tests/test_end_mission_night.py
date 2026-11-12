from datetime import timedelta

from app import db
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import AuthenticatedUserContext, CompanyFactory, UserFactory
from app.seed.helpers import get_time
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request

END_MISSION = """
    mutation (
        $missionId: Int!
        $endTime: TimeStamp!
        $pastRegistrationJustification: String
    ) {
        activities {
            endMission(
                missionId: $missionId
                endTime: $endTime
                pastRegistrationJustification: $pastRegistrationJustification
            ) {
                id
                pastRegistrationJustification
            }
        }
    }
"""


class TestEndMissionNightJustification(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.worker = UserFactory.create(post__company=self.company)

    def _mission_with_activity(self, start, reception):
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                name="Nuit",
                company=self.company,
                submitter=self.worker,
                reception_time=reception,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=reception,
                start_time=start,
                creation_time=reception,
            )
            db.session.commit()
        return mission

    def _end(self, mission, end, justification):
        return make_authenticated_request(
            time=end,
            submitter_id=self.worker.id,
            query=END_MISSION,
            variables=dict(
                mission_id=mission.id,
                end_time=end,
                past_registration_justification=justification,
            ),
        )

    def test_live_night_mission_does_not_store_justification(self):
        start = get_time(1, 23, 45)
        mission = self._mission_with_activity(start, start)
        response = self._end(mission, get_time(0, 4, 30), "Mission de nuit")
        stored = response["data"]["activities"]["endMission"][
            "pastRegistrationJustification"
        ]
        self.assertFalse(stored)

    def test_late_activity_keeps_justification(self):
        start = get_time(0, 8, 0)
        reception = start + timedelta(hours=2)
        mission = self._mission_with_activity(start, reception)
        response = self._end(mission, get_time(0, 12, 0), "Saisie après coup")
        stored = response["data"]["activities"]["endMission"][
            "pastRegistrationJustification"
        ]
        self.assertEqual(stored, "Saisie après coup")
