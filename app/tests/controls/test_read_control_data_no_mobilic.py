from datetime import datetime, date

from app.domain.controller_control import get_no_lic_observed_infractions
from app.models.controller_control import ControlType
from app.seed.factories import (
    ControllerControlFactory,
)
from app.tests.controls import ControlsTestSimple
from app.tests.helpers import (
    ApiRequests,
    make_authenticated_request,
)


class TestReadControlDataNoMobilic(ControlsTestSimple):
    def test_control_lic_papier_without_infractions(self):
        lic_papier_control = ControllerControlFactory.create(
            controller_id=self.controller_user_1.id,
            control_type=ControlType.lic_papier,
            control_bulletin={"business_id": 1},
            observed_infractions=[],
        )

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data_no_lic,
            variables=dict(
                control_id=lic_papier_control.id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )

        observed_infractions = response["data"]["controlData"][
            "observedInfractions"
        ]
        self.assertIsNotNone(observed_infractions)
        self.assertEqual(len(observed_infractions), 6)

        any_infraction = observed_infractions[0]
        self.assertIsNone(any_infraction["date"])
        self.assertFalse(any_infraction["isReported"])

    def test_control_lic_papier_with_infractions(self):
        business_id = 2
        lic_papier_control = ControllerControlFactory.create(
            controller_id=self.controller_user_1.id,
            control_type=ControlType.lic_papier,
            control_bulletin={"business_id": business_id},
            observed_infractions=get_no_lic_observed_infractions(
                date.today(), business_id
            ),
        )

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data_no_lic,
            variables=dict(
                control_id=lic_papier_control.id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )

        observed_infractions = response["data"]["controlData"][
            "observedInfractions"
        ]
        self.assertIsNotNone(observed_infractions)
        self.assertEqual(len(observed_infractions), 6)

        reported_infractions = [
            x for x in observed_infractions if x["isReported"]
        ]
        self.assertEqual(len(reported_infractions), 1)
        self.assertIsNotNone(reported_infractions[0]["date"])
