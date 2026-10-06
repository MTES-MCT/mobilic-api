import unittest
from datetime import datetime

from app.models.controller_control import ControllerControl, ControlType
from app.models.employment import Employment
from app import db
from app.seed.helpers import get_time
from app.tests.controls import ControlsTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestControlBulletinOperations(ControlsTest):
    """Tests for control bulletin operations: email sending and delivery tracking."""

    def setUp(self):
        super().setUp()
        self.send_email_query = ApiRequests.send_control_bulletin_email

    def _create_test_control(
        self,
        company_name=None,
        siren=None,
        controlled_user=None,
        control_type=ControlType.mobilic,
        qr_code_generation_time=None,
    ):
        """Create a test control with specified parameters."""
        if not controlled_user:
            controlled_user = self.employee_1

        if not company_name:
            company_name = self.company1.usual_name

        if not siren:
            siren = self.company1.siren

        if not qr_code_generation_time:
            qr_code_generation_time = datetime.now()

        control_bulletin = {"siren": siren} if siren else {}

        control_id = self._create_control(
            controlled_user=controlled_user,
            controller_user=self.controller_user_1,
            qr_code_generation_time=qr_code_generation_time,
        )

        control = ControllerControl.query.get(control_id)
        control.control_type = control_type
        control.company_name = company_name
        control.control_bulletin = control_bulletin

        db.session.commit()

        return control

    def _create_control_without_linked_user(
        self, company_name=None, siren=None
    ):
        """Create a LIC papier control with no linked User (e.g. NoLic/LIC
        papier controls), mirroring ControllerControl.create_lic_papier_control.
        """
        if not company_name:
            company_name = self.company1.usual_name

        if not siren:
            siren = self.company1.siren

        control = ControllerControl(
            control_type=ControlType.lic_papier,
            controller_id=self.controller_user_1.id,
            company_name=company_name,
            control_bulletin={"siren": siren} if siren else {},
        )
        db.session.add(control)
        db.session.commit()

        return control

    def test_send_email_with_custom_emails_updates_sent_to_admin(self):
        """Test that sending email with custom emails updates sent_to_admin flag"""
        control = self._create_test_control()

        # Initially sent_to_admin should be None/False
        self.assertFalse(control.sent_to_admin)

        custom_emails = ["test1@example.com", "test2@example.com"]

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": custom_emails,
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 2)

        # Verify that sent_to_admin is updated
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)

    def test_send_email_to_company_admin_updates_sent_to_admin(self):
        """Test that sending email to company admin updates sent_to_admin flag"""
        control = self._create_test_control()

        # Initially sent_to_admin should be None/False
        self.assertFalse(control.sent_to_admin)

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": [],  # Should find company admin automatically
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

        # Verify that sent_to_admin is updated
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)

    def test_company_matching_by_siren_works(self):
        """Test that company admin is found by SIREN in control bulletin"""
        control = self._create_test_control(siren=self.company1.siren)

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "emails": []},
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

    def test_send_email_unauthorized_user_fails(self):
        """Test that non-controller users cannot send emails"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=15),
            submitter_id=self.employee_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": ["test@example.com"],
            },
            request_by_controller_user=False,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_send_email_invalid_control_id_fails(self):
        """Test sending email with invalid control ID fails"""
        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=13),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": "99999",
                "emails": ["test@example.com"],
            },
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_send_email_missing_control_id_fails(self):
        """Test sending email without control ID parameter fails"""
        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=14),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"emails": ["test@example.com"]},
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 400},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_no_company_admin_found_returns_zero_emails(self):
        """Test when no company admin is found, zero emails are sent"""
        # Remove admin rights from all employments
        admin_employments = Employment.query.filter(
            Employment.company_id == self.company1.id,
            Employment.has_admin_rights == True,
        ).all()
        for employment in admin_employments:
            employment.has_admin_rights = False
        db.session.commit()

        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "emails": []},
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        # Should fail because no admin emails found
        self.assertIsNotNone(response.get("errors"))

    def test_control_bulletin_null_works_with_custom_emails(self):
        """Test that null control_bulletin works with custom emails"""
        control = self._create_test_control()
        control.control_bulletin = None
        db.session.commit()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": ["test@example.com"],
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

    def test_delivered_by_hand_flag_initially_false(self):
        """Test that delivered_by_hand flag is initially False"""
        control = self._create_test_control()

        # Check initial state
        self.assertFalse(control.delivered_by_hand)
        self.assertFalse(control.sent_to_admin)

    def test_mark_delivered_by_hand_updates_flag(self):
        """Test that marking as delivered by hand updates the flag"""
        control = self._create_test_control()

        # Verify initial state
        self.assertFalse(control.delivered_by_hand)
        self.assertFalse(control.sent_to_admin)

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.update_delivery_status,
            variables={"controlId": control.id, "deliveredByHand": True},
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["controllerUpdateDeliveryStatus"]
        self.assertTrue(result["deliveredByHand"])
        self.assertFalse(result["sentToAdmin"])  # Should remain False

        # Verify in database
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.delivered_by_hand)
        self.assertFalse(updated_control.sent_to_admin)

    def test_mark_delivered_by_hand_preserves_sent_to_admin(self):
        """Test that marking as delivered by hand preserves sent_to_admin flag"""
        control = self._create_test_control()

        # First send email
        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": ["test@example.com"],
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)

        # Now mark as delivered by hand
        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.update_delivery_status,
            variables={"controlId": control.id, "deliveredByHand": True},
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["controllerUpdateDeliveryStatus"]
        self.assertTrue(result["deliveredByHand"])
        self.assertTrue(
            result["sentToAdmin"]
        )  # Should remain True (email was sent)

        # Verify in database
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.delivered_by_hand)
        self.assertTrue(updated_control.sent_to_admin)  # Should remain True

    def test_update_delivery_status_unauthorized_user_fails(self):
        """Test that non-controller users cannot update delivery status"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.employee_1.id,
            query=ApiRequests.update_delivery_status,
            variables={"controlId": control.id, "deliveredByHand": True},
            request_by_controller_user=False,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_update_delivery_status_invalid_control_fails(self):
        """Test that invalid control ID fails for delivery status update"""
        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.update_delivery_status,
            variables={"controlId": 99999, "deliveredByHand": True},
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_send_email_to_driver_updates_sent_to_driver_only(self):
        """Test that sending with forAdmin=False notifies the driver, not the admin"""
        control = self._create_test_control()

        self.assertFalse(control.sent_to_admin)
        self.assertFalse(control.sent_to_driver)

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": False},
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_driver)
        self.assertFalse(updated_control.sent_to_admin)

    def test_send_email_for_admin_true_is_the_default(self):
        """Test that omitting forAdmin keeps the historical admin-sending behavior"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id)},
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])

        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)
        self.assertFalse(updated_control.sent_to_driver)

    def test_send_email_to_admin_then_driver_sets_both_flags_independently(
        self,
    ):
        """Test that a control can be sent to the admin and later to the driver"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": True},
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertIsNone(response.get("errors"))

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": False},
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertIsNone(response.get("errors"))

        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)
        self.assertTrue(updated_control.sent_to_driver)

    def test_send_email_to_driver_without_email_fails(self):
        """Test that sending to the driver fails when the control has no
        linked User (LIC papier control), and no explicit email was given"""
        control = self._create_control_without_linked_user()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": False},
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

        updated_control = ControllerControl.query.get(control.id)
        self.assertFalse(updated_control.sent_to_driver)

    def test_send_email_to_driver_with_explicit_email_for_lic_papier(self):
        """Test that an explicit email is used for the driver on a LIC papier
        control (no linked User), instead of being ignored/overridden"""
        control = self._create_control_without_linked_user()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": ["driver@example.com"],
                "forAdmin": False,
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_driver)
        self.assertFalse(updated_control.sent_to_admin)

    def test_send_email_explicit_emails_not_overridden_when_for_admin_true(
        self,
    ):
        """Test that explicit emails are still honored for the admin branch
        on a control with no linked User (regression test)"""
        control = self._create_control_without_linked_user()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={
                "controlId": str(control.id),
                "emails": ["admin@example.com"],
                "forAdmin": True,
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["sendControlBulletinEmail"]
        self.assertTrue(result["success"])
        self.assertEqual(result["nbEmailsSent"], 1)

        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)

    def test_edit_control_bulletin_blocked_after_sent_to_admin(self):
        """Test that editing the bulletin is blocked once sent to the admin"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": True},
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertIsNone(response.get("errors"))

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.controller_save_control_bulletin,
            variables={
                "controlId": control.id,
                "observation": "edited after send",
            },
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

        # sent_to_admin must remain True: the old soft-reset behavior is gone
        updated_control = ControllerControl.query.get(control.id)
        self.assertTrue(updated_control.sent_to_admin)

    def test_edit_control_bulletin_blocked_after_sent_to_driver(self):
        """Test that editing the bulletin is blocked once sent to the driver"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": False},
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertIsNone(response.get("errors"))

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.controller_save_control_bulletin,
            variables={
                "controlId": control.id,
                "observation": "edited after send",
            },
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_edit_reported_infractions_blocked_after_sent_to_driver(self):
        """Test that editing reported infractions is blocked once the
        bulletin has been sent to the driver, even though sent_to_admin is
        untouched (regression test for the sent_to_admin-only reset gap)"""
        control = self._create_test_control()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=self.send_email_query,
            variables={"controlId": str(control.id), "forAdmin": False},
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertIsNone(response.get("errors"))

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=11),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.controller_save_reported_infractions,
            variables={"controlId": control.id, "reportedInfractions": []},
            request_by_controller_user=True,
            unexposed_query=True,
            request_should_fail_with={"status": 200},
        )

        self.assertIsNotNone(response.get("errors"))

    def test_edit_control_bulletin_allowed_before_any_send(self):
        """Test that editing the bulletin is still allowed as long as it
        hasn't been sent to anyone yet"""
        control = self._create_test_control()
        # Force an update_time so we hit the "else" (edit) branch
        control.control_bulletin_creation_time = datetime.now()
        db.session.commit()

        response = make_authenticated_request(
            time=get_time(how_many_days_ago=0, hour=10),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.controller_save_control_bulletin,
            variables={
                "controlId": control.id,
                "observation": "edited before any send",
            },
            request_by_controller_user=True,
            unexposed_query=True,
        )

        self.assertIsNone(response.get("errors"))


if __name__ == "__main__":
    unittest.main()
