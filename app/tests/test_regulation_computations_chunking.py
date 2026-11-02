from datetime import date
from unittest.mock import patch

from app.domain import regulation_computations
from app.domain.regulation_computations import (
    get_admin_regulatory_computations_for_users,
)
from app.helpers.submitter_type import SubmitterType
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import RegulationComputationFactory
from app.tests import BaseTest


class TestRegulationComputationsChunking(BaseTest):
    def test_chunking_returns_every_users_computation(self):
        company = CompanyFactory.create()
        users = [UserFactory.create(post__company=company) for _ in range(5)]
        for user in users:
            RegulationComputationFactory.create(
                user=user,
                day=date(2026, 8, 20),
                submitter_type=SubmitterType.ADMIN,
            )
        user_ids = [u.id for u in users]

        with patch.object(regulation_computations, "USER_IDS_CHUNK_SIZE", 2):
            result = get_admin_regulatory_computations_for_users(
                user_ids,
                from_date=date(2026, 8, 1),
                to_date=date(2026, 8, 31),
            )

        self.assertEqual(len(result), len(users))
        self.assertEqual({rc.user_id for rc in result}, set(user_ids))
