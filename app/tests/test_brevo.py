import unittest
from app.helpers.brevo import (
    BrevoApiClient,
    GetDealData,
    UpdateDealStageData,
    GetDealsByPipelineData,
)
from app import app


class TestBrevoApiClient(unittest.TestCase):
    def setUp(self):
        self.api_key = app.config["BREVO_API_KEY"]
        if not self.api_key:
            raise ValueError(
                "API Key is missing. Ensure that BREVO_API_KEY is set correctly in the configuration."
            )

        self.brevo = BrevoApiClient(self.api_key)

        # Test Dev Churn pipeline
        self.pipeline_id = "65df0ac2fb98e37d1868b990"

        self.stage_salarie_invite = "uTJKAImu8T5Tt45pRjrYHhJ"
        self.stage_onboardee_actif = "b9fwE4p0gQTwqll1Ra0V0nQ"

        # WELI TRANSPORTS
        self.deal_id = "65e1aa297a4d8ccacd12ff3a"

    def test_get_deal(self):
        deal_data = GetDealData(deal_id=self.deal_id)
        deal_details = self.brevo.get_deal(deal_data)
        self.assertIsNotNone(deal_details, "Deal details should not be None")
        self.assertIsInstance(
            deal_details, dict, "Deal details should be a dictionary"
        )
        self.assertIn(
            "attributes",
            deal_details,
            "Deal details should contain 'attributes'",
        )
        self.assertIn(
            "deal_stage",
            deal_details["attributes"],
            "Deal details should contain 'deal_stage' attribute",
        )

    def test_get_deals_by_pipeline(self):
        data = GetDealsByPipelineData(
            pipeline_id=self.pipeline_id,
        )
        response = self.brevo.get_deals_by_pipeline(data)
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIn("items", response, "Response should contain 'items'")

    def test_get_all_pipelines(self):
        pipelines = self.brevo.get_all_pipelines()
        self.assertIsNotNone(
            pipelines, "Pipelines response should not be None"
        )
        self.assertIsInstance(pipelines, list, "Pipelines should be a list")

    def test_get_pipeline_details(self):
        pipeline_details = self.brevo.get_pipeline_details(self.pipeline_id)
        self.assertIsNotNone(
            pipeline_details, "Pipeline details should not be None"
        )
        # Vérifier que la réponse est une liste et contient au moins un élément
        self.assertIsInstance(
            pipeline_details, list, "Pipeline details should be a list"
        )
        self.assertGreater(
            len(pipeline_details),
            0,
            "Pipeline details list should not be empty",
        )

        first_pipeline = pipeline_details[0]
        self.assertIsInstance(
            first_pipeline, dict, "Each pipeline detail should be a dictionary"
        )
        self.assertIn(
            "pipeline_name",
            first_pipeline,
            "Pipeline detail should contain 'pipeline_name'",
        )

    def test_update_deal_stage(self):
        # Step 1: Update the deal to stage "onboardée et actif"
        update_data_to_active = UpdateDealStageData(
            deal_id=self.deal_id,
            pipeline_id=self.pipeline_id,
            stage_id=self.stage_onboardee_actif,
        )
        response_active = self.brevo.update_deal_stage(update_data_to_active)
        self.assertIsNotNone(
            response_active,
            "Update to 'onboardée et actif' response should not be None",
        )
        self.assertIn(
            "message",
            response_active,
            "Update response should contain a message",
        )
        self.assertEqual(
            response_active["message"], "Deal stage updated successfully"
        )
        print(f"Deal stage updated to 'onboardée et actif': {response_active}")

        # Verify the deal stage is "onboardée et actif"
        deal_data = GetDealData(deal_id=self.deal_id)
        deal_details_active = self.brevo.get_deal(deal_data)
        active_stage = deal_details_active.get("attributes", {}).get(
            "deal_stage"
        )
        active_stage_name = self.brevo.get_stage_name(
            self.pipeline_id, active_stage
        )
        expected_stage_name = self.brevo.get_stage_name(
            self.pipeline_id, self.stage_onboardee_actif
        )
        self.assertEqual(
            active_stage_name,
            expected_stage_name,
            f"Updated stage should be '{expected_stage_name}', but got '{active_stage_name}'",
        )

        # Step 2: Update the deal to stage "salarié invité"
        update_data_to_invite = UpdateDealStageData(
            deal_id=self.deal_id,
            pipeline_id=self.pipeline_id,
            stage_id=self.stage_salarie_invite,
        )
        response_invite = self.brevo.update_deal_stage(update_data_to_invite)
        self.assertIsNotNone(
            response_invite,
            "Update to 'salarié invité' response should not be None",
        )
        self.assertIn(
            "message",
            response_invite,
            "Update response should contain a message",
        )
        self.assertEqual(
            response_invite["message"], "Deal stage updated successfully"
        )
        print(f"Deal stage updated to 'salarié invité': {response_invite}")

        # Verify the deal stage is "salarié invité"
        deal_details_invite = self.brevo.get_deal(deal_data)
        invite_stage = deal_details_invite.get("attributes", {}).get(
            "deal_stage"
        )
        invite_stage_name = self.brevo.get_stage_name(
            self.pipeline_id, invite_stage
        )
        expected_invite_stage_name = self.brevo.get_stage_name(
            self.pipeline_id, self.stage_salarie_invite
        )
        self.assertEqual(
            invite_stage_name,
            expected_invite_stage_name,
            f"Updated stage should be '{expected_invite_stage_name}', but got '{invite_stage_name}'",
        )
