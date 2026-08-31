import logging
import time
import requests
import re
from typing import NamedTuple

from app import app
from app.helpers.errors import MobilicError

logger = logging.getLogger(__name__)


class LiveStormWebinar(NamedTuple):
    title: str
    link: str
    time: int


class LivestormRequestError(MobilicError):
    code = "LIVESTORM_API_ERROR"
    default_should_alert_team = False
    default_message = "Request to Livestorm API failed"


class LivestormRateLimitError(MobilicError):
    code = "LIVESTORM_RATE_LIMIT"
    default_message = "Livestorm API monthly rate limit exceeded"


class NoLivestormCredentialsError(MobilicError):
    code = "NO_LIVESTORM_CRENDENTIALS"
    default_message = "No Livestorm API credentials"


BASE_URL = "https://api.livestorm.co/v1"
UPCOMING_SESSIONS_ENDPOINT = "/sessions?filter[status]=upcoming&include=event"
MAX_PAGE_SIZE = 50
MOBILIC_EVENT_TITLE_RE = re.compile(r"\bmobilic\b", flags=re.IGNORECASE)

STATIC_FALLBACK_WEBINARS = [
    LiveStormWebinar(
        title="Webinaire Mobilic à destination des gestionnaires",
        link="https://app.livestorm.co/mte/webinaire-comment-utiliser-mobilic-session-60",
        time=1796119200,  # Dec 1, 2026 11:00 CEST
    ),
]


# API reference : https://developers.livestorm.co/reference/get_ping
class LivestormAPIClient:
    def __init__(self, api_key):
        self.api_key = api_key

    @staticmethod
    def _url_for_page_number(endpoint, number, size=MAX_PAGE_SIZE):
        formatted_query_param = f"page[size]={size}&page[number]={number}"
        prefix_symbol = "&" if "?" in endpoint else "?"
        return f"{endpoint}{prefix_symbol}{formatted_query_param}"

    # pagination doc : https://developers.livestorm.co/docs/pagination
    def _request_page_and_get_results_and_page_count(
        self, endpoint, number, **kwargs
    ):
        full_endpoint_url = f"{BASE_URL}{endpoint}"
        try:
            headers = {"Authorization": self.api_key}
            if "headers" in kwargs:
                headers.update(kwargs["headers"])
                kwargs.pop("headers")
            page_response = requests.get(
                LivestormAPIClient._url_for_page_number(
                    full_endpoint_url, number
                ),
                headers=headers,
                timeout=10,
                **kwargs,
            )
            if page_response.status_code == 429:
                raise LivestormRateLimitError()
            return page_response.json()
        except LivestormRateLimitError:
            raise
        except Exception as e:
            raise LivestormRequestError(
                f"Request to Livestorm API failed with error : {e}"
            )

    def _get_all_page_results(self, endpoint, **kwargs):
        first_page = self._request_page_and_get_results_and_page_count(
            endpoint, number=0, **kwargs
        )
        if "errors" in first_page:
            raise LivestormRequestError(
                f"Request to Livestorm API failed with error : {first_page['errors'][0]}"
            )
        page_count = first_page["meta"]["page_count"]
        results = {
            "data": first_page["data"],
            "included": first_page.get("included", []),
        }
        for next_page_number in range(1, page_count):
            next_page = self._request_page_and_get_results_and_page_count(
                endpoint, number=next_page_number, **kwargs
            )
            results["data"].extend(next_page["data"])
            results["included"].extend(next_page.get("included", []))
        return results

    def get_next_webinars(self):
        try:
            upcoming_sessions_json = self._get_all_page_results(
                UPCOMING_SESSIONS_ENDPOINT
            )
        except LivestormRateLimitError:
            logger.warning(
                "Livestorm API monthly rate limit reached (HTTP 429), returning static fallback webinars"
            )
            now = int(time.time())
            return [w for w in STATIC_FALLBACK_WEBINARS if w.time > now]
        except LivestormRequestError as e:
            logger.warning(
                f"Livestorm API unreachable (timeout or network error): {e}, returning static fallback webinars"
            )
            now = int(time.time())
            return [w for w in STATIC_FALLBACK_WEBINARS if w.time > now]

        upcoming_sessions = upcoming_sessions_json["data"]
        associated_events = upcoming_sessions_json["included"]

        mobilic_upcoming_webinars = []
        for session in upcoming_sessions:
            event = [
                e
                for e in associated_events
                if e["id"] == session["attributes"]["event_id"]
            ][0]
            if MOBILIC_EVENT_TITLE_RE.search(event["attributes"]["title"]):
                mobilic_upcoming_webinars.append(
                    LiveStormWebinar(
                        title=event["attributes"]["title"],
                        link=f'{event["attributes"]["registration_link"]}?s={session["id"]}',
                        time=session["attributes"]["estimated_started_at"],
                    )
                )
        return mobilic_upcoming_webinars


livestorm = LivestormAPIClient(app.config["LIVESTORM_API_TOKEN"])
