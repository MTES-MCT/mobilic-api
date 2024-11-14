import datetime

from app import db
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation, RegulatoryAlert, RegulationCheck
from app.models.controller_control import ControllerControl, ControlType
from app.seed import ControllerUserFactory
from app.seed.helpers import get_date
from app.tests.regulations import RegulationsTest


class TestReportInfractions(RegulationsTest):
    def test_report_infractions_take_correct_alerts(self):
        controller_user = ControllerUserFactory.create()
        work_day = get_date(how_many_days_ago=2)
        random_regulation_check = RegulationCheck.query.first()

        # order is important - this order gave a bug when the test was written
        for submitter_type in [SubmitterType.EMPLOYEE, SubmitterType.ADMIN]:
            db.session.add(
                RegulationComputation(
                    day=work_day,
                    submitter_type=submitter_type,
                    user=self.employee,
                )
            )

        db.session.add(
            RegulatoryAlert(
                day=work_day,
                submitter_type=SubmitterType.ADMIN,
                user=self.employee,
                extra={"sanction_code": "Code"},
                regulation_check=random_regulation_check,
            )
        )

        new_control = ControllerControl(
            qr_code_generation_time=datetime.datetime.now(),
            user_id=self.employee.id,
            user_first_name=self.employee.first_name,
            user_last_name=self.employee.last_name,
            control_type=ControlType.mobilic,
            controller_id=controller_user.id,
            company_name=self.company.name,
            vehicle_registration_number="AAA 11 BBB",
            nb_controlled_days=28,
        )
        db.session.add(new_control)
        db.session.commit()

        new_control.report_infractions()

        self.assertEqual(len(new_control.observed_infractions), 1)
