from unittest.mock import patch, MagicMock

from app import app, db
from app.models.notification_campaign import (
    NotificationCampaign,
    CampaignStatus,
    CampaignTargetType,
)
from app.models.push_banner_config import PushBannerConfig
from app.seed.factories import CompanyFactory, UserFactory
from app.tests import BaseTest, test_post_graphql_unexposed

CREATE_CAMPAIGN = """
    mutation ($title: String!, $body: String!,
              $targetType: CampaignTargetTypeEnum!,
              $targetUserIds: [Int]) {
        notificationCampaigns {
            createNotificationCampaign(
                title: $title, body: $body,
                targetType: $targetType,
                targetUserIds: $targetUserIds
            ) { id status }
        }
    }
"""

CANCEL_CAMPAIGN = """
    mutation ($campaignId: Int!) {
        notificationCampaigns {
            cancelNotificationCampaign(campaignId: $campaignId)
            { id status }
        }
    }
"""

UPDATE_BANNER = """
    mutation ($bannerText: String!) {
        notificationCampaigns {
            updatePushBannerText(bannerText: $bannerText)
            { success }
        }
    }
"""


def _create_campaign(bizdev, status=CampaignStatus.DRAFT):
    return NotificationCampaign(
        created_by_id=bizdev.id,
        title="Test",
        body="Body",
        target_type=CampaignTargetType.ALL_USERS,
        status=status,
    )


class TestCampaignAccess(BaseTest):
    def setUp(self):
        super().setUp()
        self.bizdev = UserFactory.create(bizdev=True)
        self.company = CompanyFactory.create()
        self.worker = UserFactory.create(
            post__company=self.company
        )
        db.session.commit()

    @patch(
        "app.controllers.notification_campaign"
        ".send_campaign_task"
    )
    def test_bizdev_can_create(self, mock_task):
        mock_task.apply_async.return_value = MagicMock(
            id="tid"
        )
        resp = test_post_graphql_unexposed(
            CREATE_CAMPAIGN,
            mock_authentication_with_user=self.bizdev,
            variables={
                "title": "T",
                "body": "B",
                "targetType": "all_users",
            },
        )
        self.assertIsNone(resp.json.get("errors"))

    @patch(
        "app.controllers.notification_campaign"
        ".send_campaign_task"
    )
    def test_worker_cannot_create(self, mock_task):
        resp = test_post_graphql_unexposed(
            CREATE_CAMPAIGN,
            mock_authentication_with_user=self.worker,
            variables={
                "title": "T",
                "body": "B",
                "targetType": "all_users",
            },
        )
        self.assertIsNotNone(resp.json.get("errors"))
        mock_task.apply_async.assert_not_called()

    def test_worker_cannot_cancel(self):
        c = _create_campaign(self.bizdev)
        db.session.add(c)
        db.session.commit()
        resp = test_post_graphql_unexposed(
            CANCEL_CAMPAIGN,
            mock_authentication_with_user=self.worker,
            variables={"campaignId": c.id},
        )
        self.assertIsNotNone(resp.json.get("errors"))

    def test_worker_cannot_update_banner(self):
        resp = test_post_graphql_unexposed(
            UPDATE_BANNER,
            mock_authentication_with_user=self.worker,
            variables={"bannerText": "test"},
        )
        self.assertIsNotNone(resp.json.get("errors"))


class TestCampaignValidation(BaseTest):
    def setUp(self):
        super().setUp()
        self.bizdev = UserFactory.create(bizdev=True)
        db.session.commit()

    @patch(
        "app.controllers.notification_campaign"
        ".send_campaign_task"
    )
    def _create(self, variables, mock_task):
        mock_task.apply_async.return_value = MagicMock(
            id="tid"
        )
        return test_post_graphql_unexposed(
            CREATE_CAMPAIGN,
            mock_authentication_with_user=self.bizdev,
            variables=variables,
        )

    def test_empty_title(self):
        resp = self._create({
            "title": "   ",
            "body": "B",
            "targetType": "all_users",
        })
        self.assertIsNotNone(resp.json.get("errors"))

    def test_title_too_long(self):
        resp = self._create({
            "title": "x" * 101,
            "body": "B",
            "targetType": "all_users",
        })
        self.assertIsNotNone(resp.json.get("errors"))

    def test_body_too_long(self):
        resp = self._create({
            "title": "T",
            "body": "x" * 501,
            "targetType": "all_users",
        })
        self.assertIsNotNone(resp.json.get("errors"))

    def test_specific_without_ids(self):
        resp = self._create({
            "title": "T",
            "body": "B",
            "targetType": "specific_employees",
        })
        self.assertIsNotNone(resp.json.get("errors"))

    def test_global_with_ids(self):
        resp = self._create({
            "title": "T",
            "body": "B",
            "targetType": "all_users",
            "targetUserIds": [1],
        })
        self.assertIsNotNone(resp.json.get("errors"))


class TestCancelCampaign(BaseTest):
    def setUp(self):
        super().setUp()
        self.bizdev = UserFactory.create(bizdev=True)
        db.session.commit()

    def test_cancel_draft(self):
        c = _create_campaign(self.bizdev)
        db.session.add(c)
        db.session.commit()
        campaign_id = c.id
        resp = test_post_graphql_unexposed(
            CANCEL_CAMPAIGN,
            mock_authentication_with_user=self.bizdev,
            variables={"campaignId": campaign_id},
        )
        self.assertIsNone(resp.json.get("errors"))
        updated = NotificationCampaign.query.get(campaign_id)
        self.assertEqual(
            updated.status, CampaignStatus.CANCELLED
        )

    def test_cannot_cancel_sent(self):
        c = _create_campaign(self.bizdev, CampaignStatus.SENT)
        db.session.add(c)
        db.session.commit()
        resp = test_post_graphql_unexposed(
            CANCEL_CAMPAIGN,
            mock_authentication_with_user=self.bizdev,
            variables={"campaignId": c.id},
        )
        self.assertIsNotNone(resp.json.get("errors"))

    def test_cancel_nonexistent(self):
        resp = test_post_graphql_unexposed(
            CANCEL_CAMPAIGN,
            mock_authentication_with_user=self.bizdev,
            variables={"campaignId": 999999},
        )
        self.assertIsNotNone(resp.json.get("errors"))


class TestBannerConfig(BaseTest):
    def setUp(self):
        super().setUp()
        self.bizdev = UserFactory.create(bizdev=True)
        db.session.commit()

    def test_create_and_update(self):
        test_post_graphql_unexposed(
            UPDATE_BANNER,
            mock_authentication_with_user=self.bizdev,
            variables={"bannerText": "Premier"},
        )
        self.assertEqual(
            PushBannerConfig.get_current().banner_text,
            "Premier",
        )
        test_post_graphql_unexposed(
            UPDATE_BANNER,
            mock_authentication_with_user=self.bizdev,
            variables={"bannerText": "Deuxieme"},
        )
        self.assertEqual(
            PushBannerConfig.get_current().banner_text,
            "Deuxieme",
        )
        self.assertEqual(PushBannerConfig.query.count(), 1)

    def test_empty_text(self):
        resp = test_post_graphql_unexposed(
            UPDATE_BANNER,
            mock_authentication_with_user=self.bizdev,
            variables={"bannerText": "   "},
        )
        self.assertIsNotNone(resp.json.get("errors"))


class TestCampaignClick(BaseTest):
    def setUp(self):
        super().setUp()
        self.bizdev = UserFactory.create(bizdev=True)
        db.session.commit()
        self.campaign = _create_campaign(
            self.bizdev, CampaignStatus.SENT
        )
        db.session.add(self.campaign)
        db.session.commit()

    def test_valid_token(self):
        from app.jobs.notification_campaign import (
            generate_click_token,
        )

        token = generate_click_token(self.campaign.id)
        with app.test_client() as c:
            resp = c.get(
                f"/campaign-click"
                f"?c={self.campaign.id}&t={token}"
            )
        self.assertEqual(resp.status_code, 204)
        db.session.refresh(self.campaign)
        self.assertEqual(self.campaign.clicked_count, 1)

    def test_invalid_token(self):
        with app.test_client() as c:
            resp = c.get(
                f"/campaign-click"
                f"?c={self.campaign.id}&t=bad"
            )
        self.assertEqual(resp.status_code, 403)

    def test_missing_params(self):
        with app.test_client() as c:
            resp = c.get("/campaign-click")
        self.assertEqual(resp.status_code, 400)
