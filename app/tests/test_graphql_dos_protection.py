import json
from unittest import TestCase

from app import app, graphql_api_path


class TestGraphQLDosProtection(TestCase):
    def setUp(self):
        app.testing = True

    def _post_graphql(self, data, content_type="application/json"):
        with app.test_client() as c, app.app_context():
            return c.post(
                graphql_api_path,
                data=(
                    json.dumps(data)
                    if isinstance(data, (dict, list))
                    else data
                ),
                content_type=content_type,
            )

    def test_normal_query_passes(self):
        response = self._post_graphql({"query": "{ __typename }"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)

    def test_many_invalid_fields_rejected_fast(self):
        """The attack vector: thousands of invalid field selections.

        Without SafeGraphQLBackend, this would take seconds due to
        O(n²) OverlappingFieldsCanBeMerged validation. With it,
        the query is still rejected (fields don't exist) but in O(n).
        """
        huge_query = "query { " + " ".join(["x"] * 3000) + " }"
        response = self._post_graphql({"query": huge_query})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("errors", data)
        self.assertIn(
            "Cannot query field",
            data["errors"][0]["message"],
        )

    def test_moderate_query_gets_full_validation(self):
        """Queries under the threshold still get full validation
        including OverlappingFieldsCanBeMerged."""
        query = "query { " + " ".join(["x"] * 50) + " }"
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("errors", data)

    def test_batch_within_limit_passes(self):
        batch = [{"query": "{ __typename }"}] * 5
        response = self._post_graphql(batch)
        self.assertEqual(response.status_code, 200)

    def test_oversized_batch_rejected(self):
        batch = [{"query": "{ __typename }"}] * 15
        response = self._post_graphql(batch)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("errors", data)
        self.assertIn("too many", data["errors"][0]["message"].lower())

    def test_invalid_body_does_not_crash(self):
        response = self._post_graphql(
            "not json at all", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
