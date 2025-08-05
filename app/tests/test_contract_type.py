from datetime import datetime, timedelta
from freezegun import freeze_time

from app import db
from app.models import Employment
from app.models.employment import ContractType
from app.tests import BaseTest
from app.seed import UserFactory, CompanyFactory


class TestContractType(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin_user = UserFactory.create(
            first_name="Admin",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.admin_employment = self.admin_user.employments[0]

        self.worker_user = UserFactory.create(
            first_name="Worker",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=False,
        )
        self.worker_employment = self.worker_user.employments[0]

    def test_contract_type_enum_values(self):
        """Test that ContractType enum has correct values"""
        self.assertEqual(ContractType.FULL_TIME, "FULL_TIME")
        self.assertEqual(ContractType.PART_TIME, "PART_TIME")

    def test_contract_type_default_none(self):
        """Test that contract_type is None by default"""
        self.assertIsNone(self.admin_employment.contract_type)
        self.assertIsNone(self.worker_employment.contract_type)

    def test_set_full_time_contract(self):
        """Test assigning a full-time contract"""
        self.admin_employment.contract_type = ContractType.FULL_TIME
        db.session.commit()

        employment = Employment.query.get(self.admin_employment.id)
        self.assertEqual(employment.contract_type, ContractType.FULL_TIME)

    def test_set_part_time_contract_with_percentage(self):
        """Test assigning a part-time contract with percentage"""
        self.admin_employment.contract_type = ContractType.PART_TIME
        self.admin_employment.part_time_percentage = 80
        db.session.commit()

        employment = Employment.query.get(self.admin_employment.id)
        self.assertEqual(employment.contract_type, ContractType.PART_TIME)
        self.assertEqual(employment.part_time_percentage, 80)

    def test_part_time_percentage_validation_valid_values(self):
        """Test that valid percentages are accepted"""
        valid_percentages = [10, 50, 80, 90]

        for percentage in valid_percentages:
            employment = Employment(
                company_id=self.company.id,
                user_id=self.worker_user.id,
                validation_status="APPROVED",
                start_date=datetime.now().date(),
                contract_type=ContractType.PART_TIME,
                part_time_percentage=percentage,
                submitter_id=self.admin_user.id,
            )

            try:
                db.session.add(employment)
                db.session.commit()
                self.assertEqual(employment.part_time_percentage, percentage)
            except Exception as e:
                self.fail(f"Valid percentage {percentage} rejected: {e}")
            finally:
                db.session.rollback()

    def test_part_time_percentage_validation_invalid_values(self):
        """Test that invalid percentages are rejected"""
        invalid_percentages = [5, 9, 91, 100, 150, -10]

        for percentage in invalid_percentages:
            employment = Employment(
                company_id=self.company.id,
                user_id=self.worker_user.id,
                validation_status="APPROVED",
                start_date=datetime.now().date(),
                contract_type=ContractType.PART_TIME,
                part_time_percentage=percentage,
                submitter_id=self.admin_user.id,
            )

            with self.assertRaises(Exception):
                db.session.add(employment)
                db.session.commit()

            db.session.rollback()

    def test_should_specify_contract_type_non_admin(self):
        """Test that non-admins don't need to specify contract type"""
        self.assertFalse(self.worker_employment.should_specify_contract_type)

    def test_should_specify_contract_type_already_specified(self):
        """Test that we don't need to specify if already done"""
        self.admin_employment.contract_type = ContractType.FULL_TIME
        db.session.commit()

        self.assertFalse(self.admin_employment.should_specify_contract_type)

    def test_should_specify_contract_type_no_snooze_yet(self):
        """Test that we need to specify if no snooze has been done yet"""
        self.assertTrue(self.admin_employment.should_specify_contract_type)

    def test_should_specify_contract_type_snooze_not_expired(self):
        """Test that we don't need to specify if snooze hasn't expired"""
        # Simulate a snooze done 10 days ago
        snooze_date = datetime.now().date() - timedelta(days=10)
        self.admin_employment.contract_type_snooze_date = snooze_date
        db.session.commit()

        self.assertFalse(self.admin_employment.should_specify_contract_type)

    def test_should_specify_contract_type_snooze_expired(self):
        """Test that we need to specify if snooze has expired (15 days passed)"""
        # Simulate a snooze done 16 days ago
        snooze_date = datetime.now().date() - timedelta(days=16)
        self.admin_employment.contract_type_snooze_date = snooze_date
        db.session.commit()

        self.assertTrue(self.admin_employment.should_specify_contract_type)

    def test_contract_type_deadline_passed_no_snooze(self):
        """Test that deadline hasn't passed if no snooze has been done"""
        self.assertFalse(self.admin_employment.contract_type_deadline_passed)

    def test_contract_type_deadline_passed_snooze_not_expired(self):
        """Test that deadline hasn't passed if snooze hasn't expired"""
        # Simulate a snooze done 14 days ago
        snooze_date = datetime.now().date() - timedelta(days=14)
        self.admin_employment.contract_type_snooze_date = snooze_date
        db.session.commit()

        self.assertFalse(self.admin_employment.contract_type_deadline_passed)

    def test_contract_type_deadline_passed_snooze_expired(self):
        """Test that deadline has passed if snooze has expired"""
        # Simulate a snooze done 16 days ago
        snooze_date = datetime.now().date() - timedelta(days=16)
        self.admin_employment.contract_type_snooze_date = snooze_date
        db.session.commit()

        self.assertTrue(self.admin_employment.contract_type_deadline_passed)

    @freeze_time("2024-01-20")
    def test_day_15_exact_behavior(self):
        """Test exact behavior on day 15"""
        # Simulate an employment created exactly 15 days ago
        with freeze_time("2024-01-05"):
            employment = Employment(
                company_id=self.company.id,
                user_id=self.admin_user.id,
                validation_status="APPROVED",
                start_date=datetime.now().date(),
                has_admin_rights=True,
                submitter_id=self.admin_user.id,
            )
            db.session.add(employment)
            db.session.commit()

        # On day 15 exactly:
        # - should_specify_contract_type = True (modal appears)
        # - contract_type_deadline_passed = False (modal can be closed)
        self.assertTrue(employment.should_specify_contract_type)
        self.assertFalse(employment.contract_type_deadline_passed)

    def test_contract_type_deadline_passed_already_specified(self):
        """Test that deadline doesn't apply if already specified"""
        self.admin_employment.contract_type = ContractType.FULL_TIME
        db.session.commit()

        self.assertFalse(self.admin_employment.contract_type_deadline_passed)

    def test_full_time_contract_no_percentage_needed(self):
        """Test that a full-time contract doesn't need percentage"""
        self.admin_employment.contract_type = ContractType.FULL_TIME
        self.admin_employment.part_time_percentage = None

        db.session.commit()

        employment = Employment.query.get(self.admin_employment.id)
        self.assertEqual(employment.contract_type, ContractType.FULL_TIME)
        self.assertIsNone(employment.part_time_percentage)

    def test_part_time_contract_can_have_null_percentage(self):
        """Test that a part-time contract can have null percentage temporarily"""
        self.admin_employment.contract_type = ContractType.PART_TIME
        self.admin_employment.part_time_percentage = None

        db.session.commit()

        employment = Employment.query.get(self.admin_employment.id)
        self.assertEqual(employment.contract_type, ContractType.PART_TIME)
        self.assertIsNone(employment.part_time_percentage)
