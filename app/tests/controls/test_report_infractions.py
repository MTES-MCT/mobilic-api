import datetime
from app import db
from app.domain.regulations import get_default_business
from app.domain.regulations_per_day import NATINF_32083
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationCheck, Business
from app.models.business import BusinessType, TransportType
from app.models.regulation_check import RegulationCheckType
from app.seed.factories import (
    RegulationComputationFactory,
    RegulatoryAlertFactory,
    ControllerControlFactory,
    ControllerUserFactory,
)
from app.seed.helpers import get_date
from app.tests.regulations import RegulationsTest

MESSAGE_EMPLOYEE = "Alerte version salarié"
MESSAGE_ADMIN = "Alerte version gestionnaire"


class TestReportInfractions(RegulationsTest):
    def setUp(self):
        super().setUp()
        self.controller_user = ControllerUserFactory.create()

    def test_report_correct_alerts_version_at_creation(self):
        how_many_days_ago = 10

        def insert_computation(submitter_type):
            RegulationComputationFactory.create(
                day=get_date(how_many_days_ago=how_many_days_ago),
                submitter_type=submitter_type,
                user=self.employee,
            )

        def insert_alert(message, submitter_type):
            RegulatoryAlertFactory.create(
                day=get_date(how_many_days_ago=10),
                submitter_type=submitter_type,
                user=self.employee,
                regulation_check=RegulationCheck.query.filter(
                    RegulationCheck.type
                    == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ).first(),
                extra=dict(sanction_code=NATINF_32083, message=message),
                business=get_default_business(),
            )

        insert_computation(submitter_type=SubmitterType.EMPLOYEE)
        insert_alert(
            message=MESSAGE_EMPLOYEE, submitter_type=SubmitterType.EMPLOYEE
        )

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
        )
        control.report_infractions()
        self.assertEqual(1, len(control.observed_infractions))
        self.assertEqual(
            MESSAGE_EMPLOYEE,
            control.observed_infractions[0]["extra"]["message"],
        )

        insert_computation(submitter_type=SubmitterType.ADMIN)
        insert_alert(message=MESSAGE_ADMIN, submitter_type=SubmitterType.ADMIN)
        control.report_infractions()
        self.assertEqual(1, len(control.observed_infractions))
        self.assertEqual(
            MESSAGE_ADMIN, control.observed_infractions[0]["extra"]["message"]
        )

    def test_mobilic_control_adds_no_lic_infraction_when_current_day_not_filled_trm(
        self,
    ):
        """
        Test that NO_LIC infraction is added when current day is not filled.
        For TRM (Transport de Marchandises): NATINF 23103
        """
        trm_business = Business.query.filter(
            Business.transport_type == TransportType.TRM,
            Business.business_type == BusinessType.SHIPPING,
        ).first()
        self.employee.employments[0].business = trm_business
        db.session.commit()

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
            qr_code_generation_time=datetime.datetime.now(),
            control_bulletin={"business_id": trm_business.id},
        )

        control.report_infractions()

        self.assertEqual(1, len(control.observed_infractions))
        infraction = control.observed_infractions[0]

        self.assertEqual(RegulationCheckType.NO_LIC, infraction["check_type"])
        self.assertTrue(infraction["is_reported"])
        self.assertTrue(infraction["is_reportable"])
        self.assertEqual("NATINF 23103", infraction["sanction"])
        self.assertEqual(trm_business.id, infraction["business_id"])
        self.assertEqual(
            control.history_end_date.isoformat(), infraction["date"]
        )

    def test_mobilic_control_adds_no_lic_infraction_when_current_day_not_filled_trv(
        self,
    ):
        """
        Test that NO_LIC infraction is added when current day is not filled.
        For TRV (Transport de Voyageurs): NATINF 25666
        """
        trv_business = Business.query.filter(
            Business.transport_type == TransportType.TRV,
            Business.business_type == BusinessType.VTC,
        ).first()
        self.employee.employments[0].business = trv_business
        db.session.commit()

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
            qr_code_generation_time=datetime.datetime.now(),
            control_bulletin={"business_id": trv_business.id},
        )

        control.report_infractions()

        self.assertEqual(1, len(control.observed_infractions))
        infraction = control.observed_infractions[0]

        self.assertEqual(RegulationCheckType.NO_LIC, infraction["check_type"])
        self.assertTrue(infraction["is_reported"])
        self.assertTrue(infraction["is_reportable"])
        self.assertEqual("NATINF 25666", infraction["sanction"])
        self.assertEqual(trv_business.id, infraction["business_id"])
        self.assertEqual(
            control.history_end_date.isoformat(), infraction["date"]
        )

    def test_no_lic_infraction_uses_employment_business_id_as_fallback(self):
        """
        Test that NO_LIC infraction uses employment business_id as fallback
        when control bulletin doesn't have one.
        """
        trm_business = Business.query.filter(
            Business.transport_type == TransportType.TRM
        ).first()
        self.employee.employments[0].business = trm_business
        db.session.commit()

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
            qr_code_generation_time=datetime.datetime.now(),
            control_bulletin={},
        )

        control.report_infractions()

        self.assertEqual(1, len(control.observed_infractions))
        infraction = control.observed_infractions[0]
        self.assertEqual(RegulationCheckType.NO_LIC, infraction["check_type"])
        self.assertEqual("NATINF 23103", infraction["sanction"])
        self.assertEqual(trm_business.id, infraction["business_id"])

    def test_no_lic_infraction_not_added_when_current_day_has_activities(self):
        """
        Test that NO_LIC infraction is NOT added when current day has activities.
        """
        trm_business = Business.query.filter(
            Business.transport_type == TransportType.TRM
        ).first()
        self.employee.employments[0].business = trm_business
        db.session.commit()

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
            qr_code_generation_time=datetime.datetime.now(),
            control_bulletin={"business_id": trm_business.id},
        )

        start = datetime.datetime.combine(
            control.history_end_date, datetime.time(8, 0)
        )
        end = datetime.datetime.combine(
            control.history_end_date, datetime.time(12, 0)
        )

        self._log_and_validate_mission(
            mission_name="Test mission",
            submitter=self.employee,
            work_periods=[(start, end)],
            reception_time=start,
        )

        control.report_infractions()

        self.assertEqual(0, len(control.observed_infractions))

    def test_no_lic_infraction_not_added_when_no_business_id_available(self):
        """
        Test that NO_LIC infraction is NOT added when no business_id is available.
        """
        self.employee.employments[0].business = None
        db.session.commit()

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
            qr_code_generation_time=datetime.datetime.now(),
            control_bulletin={},
        )

        control.report_infractions()

        self.assertEqual(0, len(control.observed_infractions))
