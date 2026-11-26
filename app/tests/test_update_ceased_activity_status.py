from unittest.mock import MagicMock, patch

from app import db
from app.domain.company import job_update_ceased_activity_status
from app.helpers.oauth.models import OAuth2Client, ThirdPartyClientEmployment
from app.helpers.siren import SIREN_API_MIN_SECONDS_BETWEEN_REQUESTS
from app.models import Company, Employment
from app.models.employment import EmploymentRequestValidationStatus
from app.seed.factories import (
    CompanyFactory,
    EmploymentFactory,
    ThirdPartyClientEmploymentFactory,
)
from app.tests import BaseTest


class TestUpdateCeasedActivityStatus(BaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.company = CompanyFactory.create(siren="123456789")
        self.pending_employment = EmploymentFactory.create(
            company=self.company,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            validation_time=None,
        )
        client = OAuth2Client.create_client(
            name="editor", redirect_uris="http://localhost:3000"
        )
        ThirdPartyClientEmploymentFactory.create(
            employment=self.pending_employment,
            client=client,
            invitation_token="token",
        )
        db.session.commit()

    @patch("app.domain.company.time.sleep")
    @patch("app.domain.company.siren_api_client.has_company_ceased_activity")
    def test_siren_api_calls_are_spaced_to_respect_rate_limit(
        self, has_company_ceased_activity: MagicMock, sleep: MagicMock
    ) -> None:
        CompanyFactory.create(siren="987654321")
        has_company_ceased_activity.return_value = (False, {})

        job_update_ceased_activity_status()

        self.assertEqual(has_company_ceased_activity.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(SIREN_API_MIN_SECONDS_BETWEEN_REQUESTS)

    @patch("app.domain.company.time.sleep")
    @patch("app.domain.company.siren_api_client.has_company_ceased_activity")
    def test_pending_employment_linked_to_third_party_is_deleted(
        self, has_company_ceased_activity: MagicMock, _sleep: MagicMock
    ) -> None:
        has_company_ceased_activity.return_value = (True, {})

        job_update_ceased_activity_status()

        self.assertTrue(Company.query.get(self.company.id).has_ceased_activity)
        self.assertIsNone(Employment.query.get(self.pending_employment.id))
        self.assertEqual(ThirdPartyClientEmployment.query.count(), 0)
