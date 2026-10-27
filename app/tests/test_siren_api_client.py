from unittest import TestCase
from unittest.mock import patch, MagicMock

from app.helpers.siren import SirenAPIClient


def _page_response(facilities, cursor, next_cursor, total):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "header": {
            "curseur": cursor,
            "curseurSuivant": next_cursor,
            "total": total,
        },
        "etablissements": facilities,
    }
    return response


class TestSirenAPIClientPagination(TestCase):
    def setUp(self):
        self.client = SirenAPIClient("dummy-api-key")

    @patch("app.helpers.siren.requests.get")
    def test_single_page_returns_all_facilities(self, mock_get):
        facilities = [{"siret": f"{i:014}"} for i in range(3)]
        mock_get.return_value = _page_response(
            facilities, cursor="*", next_cursor="*", total=3
        )

        info = self.client._request_siren_info("123456789")

        self.assertEqual(len(info["etablissements"]), 3)
        self.assertEqual(mock_get.call_count, 1)

    @patch("app.helpers.siren.requests.get")
    def test_facilities_beyond_first_page_are_returned(self, mock_get):
        # Reproduces card 2648/2763 : SIREN with more facilities than the
        # page size, the last ones (e.g. 39102934501031) were dropped.
        page_1 = [{"siret": f"{i:014}"} for i in range(1000)]
        page_2 = [{"siret": "39102934501031"}]
        mock_get.side_effect = [
            _page_response(page_1, cursor="*", next_cursor="abc", total=1001),
            _page_response(
                page_2, cursor="abc", next_cursor="abc", total=1001
            ),
        ]

        info = self.client._request_siren_info("391029345")

        self.assertEqual(len(info["etablissements"]), 1001)
        sirets = [f["siret"] for f in info["etablissements"]]
        self.assertIn("39102934501031", sirets)
        self.assertEqual(mock_get.call_count, 2)
        second_call_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_call_params["curseur"], "abc")

    @patch("app.helpers.siren.requests.get")
    def test_pagination_stops_without_next_cursor(self, mock_get):
        mock_get.return_value = _page_response(
            [{"siret": "00000000000001"}],
            cursor="*",
            next_cursor=None,
            total=1,
        )

        info = self.client._request_siren_info("123456789")

        self.assertEqual(len(info["etablissements"]), 1)
        self.assertEqual(mock_get.call_count, 1)
