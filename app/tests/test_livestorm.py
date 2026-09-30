import json
from unittest.mock import patch, MagicMock

from app import app
from app.controllers.misc import refresh_webinars_cache, WEBINARS_CACHE_KEY
from app.helpers.livestorm import livestorm, LivestormRateLimitError
from app.tests import BaseTest


def generate_livestorm_response_payload(
    number_of_pages, event_title="Webinaire Mobilic"
):
    raw_json = (
        '{"data":[{"id":"487","type":"sessions","attributes":{"event_id":"3b0","status":"upcoming","timezone":"Europe/Paris","room_link":"https://app.livestorm.co","attendees_count":0,"duration":null,"estimated_started_at":1638880200,"started_at":0,"ended_at":0,"canceled_at":0,"created_at":1625046453,"updated_at":1631002598,"registrants_count":54},"relationships":{"event":{"data":{"type":"events","id":"3b0"}}}},{"id":"4d9","type":"sessions","attributes":{"event_id":"3b0","status":"upcoming","timezone":"Europe/Paris","room_link":"https://app.livestorm.co","attendees_count":0,"duration":null,"estimated_started_at":1635856200,"started_at":0,"ended_at":0,"canceled_at":0,"created_at":1625046453,"updated_at":1630996348,"registrants_count":52},"relationships":{"event":{"data":{"type":"events","id":"3b0"}}}}],"included":[{"id":"3b0","type":"events","attributes":{"title":"'
        + event_title
        + '","slug":"bla-bla-bla-3","registration_link":"https://app.livestorm.co","estimated_duration":30,"registration_page_enabled":true,"everyone_can_speak":false,"description":null,"status":"published","light_registration_page_enabled":true,"recording_enabled":true,"recording_public":null,"show_in_company_page":false,"chat_enabled":true,"polls_enabled":true,"questions_enabled":true,"language":"fr","published_at":1624092934,"created_at":1624092921,"updated_at":1631524373,"owner":{"id":"2fb","type":"people","attributes":{"role":"team_member","created_at":1611935738,"updated_at":1631524373,"timezone":"Europe/Paris","first_name":"Equipe","last_name":"BLA BLA","email":"blabla","avatar_link":null}},"sessions_count":5,"fields":[{"id":"email","type":"text","order":0,"required":true},{"id":"first_name","type":"text","order":1,"required":true},{"id":"last_name","type":"text","order":2,"required":true},{"id":"avatar","type":"file","order":3,"required":false}]}}],"meta":{"record_count":'
        + str(2 * number_of_pages)
        + ',"page_count":'
        + str(number_of_pages)
        + ',"items_per_page":2}}'
    )
    return json.loads(raw_json)


LIVESTORM_ENDPOINT = "/sessions?filter[status]=upcoming&include=event"
MOBILIC_WEBINARS_ENDPOINT = "/next-webinars"


class TestLiveStormWebinars(BaseTest):
    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    def test_livestorm_pagination(self, mock):
        for number_of_pages in [1, 2, 3, 5, 10]:
            mock.reset_mock()
            mock.side_effect = (
                lambda *args, **kwargs: generate_livestorm_response_payload(
                    number_of_pages
                )
            )
            webinars = livestorm.get_next_webinars()
            self.assertEqual(mock.call_count, number_of_pages)
            for page_number in range(0, number_of_pages):
                mock.assert_any_call(LIVESTORM_ENDPOINT, number=page_number)
            self.assertEqual(len(webinars), 2 * number_of_pages)

    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    def test_livestorm_request_only_returns_mobilic_events(self, mock):
        mock.side_effect = (
            lambda *args, **kwargs: generate_livestorm_response_payload(
                2, "Webinaire beta.gouv"
            )
        )
        webinars = livestorm.get_next_webinars()
        self.assertEqual(len(webinars), 0)

        mock.reset_mock()
        mock.side_effect = (
            lambda *args, **kwargs: generate_livestorm_response_payload(
                2, "Présentation Mobilic"
            )
        )
        webinars = livestorm.get_next_webinars()
        self.assertEqual(len(webinars), 4)

    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    @patch("app.controllers.misc.get_redis_client")
    def test_webinars_endpoint_reads_from_cache(
        self, mock_redis_factory, mock
    ):
        app.config["LIVESTORM_API_TOKEN"] = "abc"
        cached = json.dumps([{"title": "t", "link": "l", "time": 1}])
        mock_redis_factory.return_value = MagicMock(get=lambda k: cached)

        with app.test_client() as c:
            webinars_response = c.get(MOBILIC_WEBINARS_ENDPOINT)
            self.assertEqual(webinars_response.status_code, 200)
            self.assertEqual(len(webinars_response.json), 1)
        # the endpoint must never call Livestorm, it only reads the cache
        mock.assert_not_called()

    @patch("app.controllers.misc.get_redis_client")
    def test_webinars_endpoint_returns_empty_when_cache_cold(
        self, mock_redis_factory
    ):
        app.config["LIVESTORM_API_TOKEN"] = "abc"
        mock_redis_factory.return_value = MagicMock(get=lambda k: None)

        with app.test_client() as c:
            webinars_response = c.get(MOBILIC_WEBINARS_ENDPOINT)
            self.assertEqual(webinars_response.status_code, 200)
            self.assertEqual(webinars_response.json, [])

    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    @patch("app.controllers.misc.get_redis_client")
    def test_refresh_webinars_cache_writes_livestorm_data(
        self, mock_redis_factory, mock
    ):
        app.config["LIVESTORM_API_TOKEN"] = "abc"
        store = {}
        mock_redis_factory.return_value = MagicMock(
            setex=lambda k, t, v: store.__setitem__(k, v)
        )
        mock.side_effect = (
            lambda *args, **kwargs: generate_livestorm_response_payload(
                2, "Présentation Mobilic"
            )
        )

        refresh_webinars_cache()

        self.assertIn(WEBINARS_CACHE_KEY, store)
        self.assertEqual(len(json.loads(store[WEBINARS_CACHE_KEY])), 4)

    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    @patch("app.controllers.misc.get_redis_client")
    def test_refresh_webinars_cache_writes_fallback_on_rate_limit(
        self, mock_redis_factory, mock
    ):
        app.config["LIVESTORM_API_TOKEN"] = "abc"
        store = {}
        mock_redis_factory.return_value = MagicMock(
            setex=lambda k, t, v: store.__setitem__(k, v)
        )
        mock.side_effect = LivestormRateLimitError()

        refresh_webinars_cache()

        cached = json.loads(store[WEBINARS_CACHE_KEY])
        self.assertGreater(len(cached), 0)
        for webinar in cached:
            self.assertIn("title", webinar)
            self.assertIn("link", webinar)
            self.assertIn("time", webinar)

    @patch("app.helpers.livestorm.time")
    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    def test_fallback_filters_past_sessions(self, mock_request, mock_time):
        # Simulate being far in the future so all fallback sessions are in the past
        mock_time.time.return_value = 9999999999
        mock_request.side_effect = LivestormRateLimitError()

        webinars = livestorm.get_next_webinars()
        self.assertEqual(len(webinars), 0)

    @patch(
        "app.helpers.livestorm.LivestormAPIClient._request_page_and_get_results_and_page_count"
    )
    @patch("app.controllers.misc.get_redis_client")
    def test_webinars_endpoint_returns_empty_when_redis_unavailable(
        self, mock_redis_factory, mock
    ):
        app.config["LIVESTORM_API_TOKEN"] = "abc"
        mock_redis_factory.side_effect = Exception("Redis connection failed")

        with app.test_client() as c:
            webinars_response = c.get(MOBILIC_WEBINARS_ENDPOINT)
            self.assertEqual(webinars_response.status_code, 200)
            self.assertEqual(webinars_response.json, [])
        # a Redis outage must not trigger a Livestorm call from the web worker
        mock.assert_not_called()
