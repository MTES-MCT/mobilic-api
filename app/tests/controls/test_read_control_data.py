from datetime import datetime

from app.domain.regulations import get_default_business
from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import RegulationCheckType, RegulationCheck
from app.seed.factories import (
    RegulationComputationFactory,
    RegulatoryAlertFactory,
)
from app.seed.helpers import get_date
from app.tests.controls import ControlsTestSimple
from app.tests.helpers import (
    ApiRequests,
    make_authenticated_request,
)


class TestReadControlData(ControlsTestSimple):
    def test_read_control_data(self):
        control_id = self._create_control(
            controller_user=self.controller_user_1,
            controlled_user=self.controlled_user_1,
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertEqual(response["data"]["controlData"]["id"], control_id)

    def test_can_not_read_control_of_other_controller(self):
        control_id = self._create_control(
            controller_user=self.controller_user_2,
            controlled_user=self.controlled_user_1,
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )

    def test_can_read_alerts(self):
        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=30),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user_1,
        )

        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user_1,
        )

        regulation_check = RegulationCheck.query.first()
        # init_businesses_data()

        RegulatoryAlertFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user_1,
            regulation_check=regulation_check,
            business=get_default_business(),
        )

        control_id = self._create_control(
            controller_user=self.controller_user_1,
            controlled_user=self.controlled_user_1,
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data_with_alerts,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        regulations_by_day = response["data"]["controlData"][
            "regulationComputationsByDay"
        ]
        self.assertEqual(len(regulations_by_day), 1)

        first_day_regulations = regulations_by_day[0]["regulationComputations"]
        self.assertEqual(
            len(first_day_regulations[0]["regulationChecks"]),
            7,
        )
        checks = [
            c
            for c in first_day_regulations[0]["regulationChecks"]
            if c is not None
        ]
        minimumDailyRestCheck = [
            c
            for c in checks
            if c["type"] == RegulationCheckType.MINIMUM_DAILY_REST
        ][0]
        minimumWorkDayBreakCheck = [
            c
            for c in checks
            if c["type"] == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        ][0]
        self.assertIsNotNone(minimumDailyRestCheck["alert"])
        self.assertIsNone(minimumWorkDayBreakCheck["alert"])
