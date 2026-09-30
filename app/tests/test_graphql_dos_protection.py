import json
from unittest import TestCase

from app import app, graphql_api_path
from app.helpers.graphql import GRAPHQL_MAX_DEPTH, GRAPHQL_MAX_FIELDS


def _nested(depth):
    return "query " + "{ f " * depth + "}" * depth


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

    def _message(self, response):
        return response.get_json()["errors"][0]["message"].lower()

    def test_normal_query_passes(self):
        response = self._post_graphql({"query": "{ __typename }"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)

    def test_field_count_at_limit_passes_cap(self):
        query = "query { " + " ".join(["x"] * GRAPHQL_MAX_FIELDS) + " }"
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("too large", self._message(response))
        self.assertIn("cannot query field", self._message(response))

    def test_field_count_over_limit_rejected(self):
        query = "query { " + " ".join(["x"] * (GRAPHQL_MAX_FIELDS + 1)) + " }"
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", self._message(response))

    def test_alias_overloading_counted_as_fields(self):
        n = GRAPHQL_MAX_FIELDS + 1
        query = "query { " + " ".join(f"a{i}: x" for i in range(n)) + " }"
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", self._message(response))

    def test_depth_at_limit_passes_cap(self):
        response = self._post_graphql({"query": _nested(GRAPHQL_MAX_DEPTH)})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("too deep", self._message(response))

    def test_depth_over_limit_rejected(self):
        response = self._post_graphql(
            {"query": _nested(GRAPHQL_MAX_DEPTH + 1)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("too deep", self._message(response))

    def test_depth_hidden_behind_fragment_rejected(self):
        deep = "{ f " * (GRAPHQL_MAX_DEPTH + 1) + "}" * (GRAPHQL_MAX_DEPTH + 1)
        query = "query { ...A } fragment A on Query " + deep
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)
        self.assertIn("too deep", self._message(response))

    def test_cyclic_fragment_does_not_hang(self):
        query = (
            "query { ...A } "
            "fragment A on Query { f { ...B } } "
            "fragment B on Query { f { ...A } }"
        )
        response = self._post_graphql({"query": query})
        self.assertEqual(response.status_code, 400)

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

    def test_oversized_payload_rejected(self):
        """Requests exceeding MAX_CONTENT_LENGTH should be rejected."""
        # Create a payload just over 10MB
        huge_payload = {"query": "x" * (11 * 1024 * 1024)}
        response = self._post_graphql(huge_payload)
        self.assertEqual(response.status_code, 413)
