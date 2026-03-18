from datetime import date, timedelta
from unittest.mock import patch

from app.models import User, Company, Employment
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.tests import BaseTest
from app import app


def test_post_rest_authenticated(url, json, user):
    """Helper to test REST endpoints with authentication"""
    with app.test_client(
        mock_authentication_with_user=user
    ) as c, app.app_context():
        return c.post(url, json=json)


class TestValidateExportParams(BaseTest):
    def setUp(self):
        super().setUp()

        self.company = CompanyFactory.create(
            usual_name="Test Company",
            siren="123456789",
        )

        self.admin = UserFactory.create(
            email="admin@test.com",
            first_name="Admin",
            last_name="Test",
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=self.admin,
            has_admin_rights=True,
        )

        self.employees = []
        for i in range(5):
            employee = UserFactory.create(
                email=f"employee{i}@test.com",
                first_name=f"Employee{i}",
                last_name=f"Test{i}",
            )
            EmploymentFactory.create(
                company=self.company,
                submitter=self.admin,
                user=employee,
                has_admin_rights=False,
            )
            self.employees.append(employee)

    ## tests validation

    def test_validation_single_or_consolidated_strategy(self):
        """Test nominal case: < 31 days and < 100 users → can choose consolidated"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",  # 15 days
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["strategy"], "single_or_consolidated")
        self.assertTrue(data["can_choose_consolidated"])
        self.assertIn("one_file_by_employee", data["message"])
        self.assertEqual(data["num_chunks"], 1)

    def test_validation_over_31_days_strategy(self):
        """Test period > 31 days → OVER_31_DAYS strategy"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-03-15",  # > 31 days
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["strategy"], "over_31_days")
        self.assertFalse(data["can_choose_consolidated"])
        self.assertIn("31 jours", data["message"])
        self.assertIn("mois", data["message"])
        self.assertGreater(data["num_chunks"], 1)

    def test_validation_over_365_days_strategy(self):
        """Test period >= 365 days → OVER_365_DAYS strategy"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2023-01-01",
                "max_date": "2025-12-31",  # More than 2 years
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["strategy"], "over_365_days")
        self.assertFalse(data["can_choose_consolidated"])
        self.assertIn("1 an", data["message"])
        self.assertIn("salarié", data["message"])
        # Should have multiple chunks (one per year per employee)
        self.assertGreater(data["num_chunks"], 1)

    def test_validation_over_100_users_strategy(self):
        """Test > 100 users → OVER_100_USERS strategy"""
        # Create 101 additional employees
        for i in range(101):
            employee = UserFactory.create(
                email=f"bulk_employee{i}@test.com",
                first_name=f"Bulk{i}",
                last_name=f"Employee{i}",
            )
            EmploymentFactory.create(
                company=self.company,
                submitter=self.admin,
                user=employee,
                has_admin_rights=False,
            )

        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",  # < 31 days
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["strategy"], "over_100_users")
        self.assertFalse(data["can_choose_consolidated"])
        self.assertIn("100", data["message"])
        self.assertIn("tranche", data["message"])
        # Should have at least 2 chunks (106 users / 100)
        self.assertGreaterEqual(data["num_chunks"], 2)

    def test_validation_with_detailed_true(self):
        """Test with detailed=true → returns chunk details"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-03-15",
                "detailed": True,
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertIn("chunks", data)
        self.assertIsInstance(data["chunks"], list)
        self.assertGreater(len(data["chunks"]), 0)

        # Check chunk structure
        chunk = data["chunks"][0]
        self.assertIn("user_ids", chunk)
        self.assertIn("min_date", chunk)
        self.assertIn("max_date", chunk)
        self.assertIn("file_suffix", chunk)
        self.assertIsInstance(chunk["user_ids"], list)

    def test_validation_without_detailed(self):
        """Test without detailed → no chunks in response"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertNotIn("chunks", data)

    def test_validation_without_min_date_fallback(self):
        """Test without min_date → fallback to 1 year back"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "max_date": date.today().isoformat(),
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        # With 1 year of data and < 100 users, should be OVER_365_DAYS
        self.assertEqual(data["strategy"], "over_365_days")

    def test_validation_without_user_ids(self):
        """Test without user_ids → all company users"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        # Should include all employees (admin + 5 employees = 6)
        self.assertEqual(response.json["num_chunks"], 1)

    def test_validation_with_specific_user_ids(self):
        """Test with specific user_ids"""
        user_ids = [self.employees[0].id, self.employees[1].id]

        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [self.company.id],
                "user_ids": user_ids,
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",
                "detailed": True,
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json
        # Check that only specified users are in chunks
        chunk = data["chunks"][0]
        self.assertEqual(len(chunk["user_ids"]), 2)
        self.assertCountEqual(chunk["user_ids"], user_ids)

    def test_validation_unauthorized_company(self):
        """Test access to unauthorized company → 403 error"""
        other_company = CompanyFactory.create(
            usual_name="Other Company",
            siren="987654321",
        )

        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "company_ids": [other_company.id],
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 403)

    def test_validation_missing_company_ids(self):
        """Test without company_ids → 422 error"""
        response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={
                "min_date": "2025-01-01",
                "max_date": "2025-01-15",
            },
            user=self.admin,
        )

        self.assertEqual(response.status_code, 422)

    ## tests validation + export

    @patch("app.services.exports.async_export_excel.delay")
    def test_validation_matches_export_single_or_consolidated(
        self, mock_celery_delay
    ):
        """Test validation/export consistency for SINGLE_OR_CONSOLIDATED strategy"""
        params = {
            "company_ids": [self.company.id],
            "min_date": "2025-01-01",
            "max_date": "2025-01-15",
            "one_file_by_employee": False,
        }

        # 1. Call validation
        validation_response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={**params, "detailed": True},
            user=self.admin,
        )

        self.assertEqual(validation_response.status_code, 200)
        predicted_data = validation_response.json
        predicted_strategy = predicted_data["strategy"]
        predicted_chunks = predicted_data["chunks"]
        predicted_num_chunks = predicted_data["num_chunks"]

        # 2. Call export with same parameters
        export_response = test_post_rest_authenticated(
            "/companies/download_activity_report",
            json=params,
            user=self.admin,
        )

        self.assertEqual(export_response.status_code, 202)

        # 3. Check that Celery was called
        mock_celery_delay.assert_called_once()

        # 4. Get chunks passed to Celery
        call_kwargs = mock_celery_delay.call_args[1]
        actual_chunks = call_kwargs["chunks"]

        # 5. Compare validation vs export
        self.assertEqual(predicted_num_chunks, len(actual_chunks))
        self.assertEqual(predicted_strategy, actual_chunks[0]["strategy"])

        for predicted, actual in zip(predicted_chunks, actual_chunks):
            self.assertEqual(predicted["min_date"], actual["min_date"])
            self.assertEqual(predicted["max_date"], actual["max_date"])
            self.assertCountEqual(predicted["user_ids"], actual["user_ids"])
            self.assertEqual(predicted["file_suffix"], actual["file_suffix"])

    @patch("app.services.exports.async_export_excel.delay")
    def test_validation_matches_export_over_31_days(self, mock_celery_delay):
        """Test validation/export consistency for OVER_31_DAYS strategy"""
        params = {
            "company_ids": [self.company.id],
            "min_date": "2025-01-01",
            "max_date": "2025-03-15",
        }

        validation_response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={**params, "detailed": True},
            user=self.admin,
        )

        predicted_data = validation_response.json
        self.assertEqual(predicted_data["strategy"], "over_31_days")

        export_response = test_post_rest_authenticated(
            "/companies/download_activity_report",
            json=params,
            user=self.admin,
        )

        self.assertEqual(export_response.status_code, 202)

        call_kwargs = mock_celery_delay.call_args[1]
        actual_chunks = call_kwargs["chunks"]

        self.assertEqual(len(predicted_data["chunks"]), len(actual_chunks))
        self.assertEqual("over_31_days", actual_chunks[0]["strategy"])

        for predicted, actual in zip(predicted_data["chunks"], actual_chunks):
            self.assertEqual(predicted["min_date"], actual["min_date"])
            self.assertEqual(predicted["max_date"], actual["max_date"])
            self.assertCountEqual(predicted["user_ids"], actual["user_ids"])

    @patch("app.services.exports.async_export_excel.delay")
    def test_validation_matches_export_over_365_days(self, mock_celery_delay):
        """Test validation/export consistency for OVER_365_DAYS strategy"""
        params = {
            "company_ids": [self.company.id],
            "min_date": "2023-01-01",
            "max_date": "2025-12-31",
        }

        validation_response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json={**params, "detailed": True},
            user=self.admin,
        )

        predicted_data = validation_response.json
        self.assertEqual(predicted_data["strategy"], "over_365_days")

        export_response = test_post_rest_authenticated(
            "/companies/download_activity_report",
            json=params,
            user=self.admin,
        )

        self.assertEqual(export_response.status_code, 202)

        call_kwargs = mock_celery_delay.call_args[1]
        actual_chunks = call_kwargs["chunks"]

        self.assertEqual(len(predicted_data["chunks"]), len(actual_chunks))
        self.assertEqual("over_365_days", actual_chunks[0]["strategy"])

        for predicted, actual in zip(
            predicted_data["chunks"][:3], actual_chunks[:3]
        ):
            self.assertEqual(predicted["min_date"], actual["min_date"])
            self.assertEqual(predicted["max_date"], actual["max_date"])
            self.assertCountEqual(predicted["user_ids"], actual["user_ids"])

    @patch("app.services.exports.async_export_excel.delay")
    def test_validation_one_file_by_employee_ignored_when_chunking(
        self, mock_celery_delay
    ):
        """Test that one_file_by_employee is ignored during automatic chunking"""
        params = {
            "company_ids": [self.company.id],
            "min_date": "2025-01-01",
            "max_date": "2025-03-15",  # > 31 days → OVER_31_DAYS
            "one_file_by_employee": True,  # Should be ignored
        }

        validation_response = test_post_rest_authenticated(
            "/companies/validate_export_params",
            json=params,
            user=self.admin,
        )

        self.assertFalse(validation_response.json["can_choose_consolidated"])

        export_response = test_post_rest_authenticated(
            "/companies/download_activity_report",
            json=params,
            user=self.admin,
        )

        self.assertEqual(export_response.status_code, 202)

        call_kwargs = mock_celery_delay.call_args[1]
        actual_chunks = call_kwargs["chunks"]

        self.assertEqual(actual_chunks[0]["strategy"], "over_31_days")

        self.assertGreater(len(actual_chunks), 1)
