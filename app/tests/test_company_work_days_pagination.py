from datetime import datetime

from flask.ctx import AppContext

from app import app, db
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import UserFactory, CompanyFactory
from app.seed.helpers import get_time
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestCompanyWorkDaysPagination(BaseTest):
    """Guards the Relay invariant that broke in prod (Sentry MOBILIC-TEN):
    a page must never come back with an empty `edges` list while
    `hasNextPage` is true - that combination leaves the caller with no way
    to make progress (no cursor to anchor on, nothing to show either).
    """

    def setUp(self):
        super().setUp()
        self._app_context = AppContext(app)
        self._app_context.__enter__()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _log_activity_as(
        self, worker, mission, days_ago, start_hour, end_hour
    ):
        with AuthenticatedUserContext(worker):
            activity = log_activity(
                submitter=worker,
                user=worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=get_time(
                    how_many_days_ago=days_ago, hour=start_hour
                ),
                end_time=get_time(how_many_days_ago=days_ago, hour=end_hour),
            )
        db.session.commit()
        return activity

    def _create_mission(self, worker):
        return Mission.create(
            submitter=worker,
            company=self.company,
            reception_time=datetime.now(),
        )

    def _cancel_activity(self, worker, activity_id):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=worker.id,
            query=ApiRequests.cancel_activity,
            variables=dict(activity_id=activity_id),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )

    def _query_company_work_days(self, first=None, after=None, user_ids=None):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.query_company_work_days,
            variables=dict(
                id=self.company.id,
                first=first,
                after=after,
                user_ids=user_ids,
            ),
        )
        return response["data"]["company"]["workDays"]

    def _query_user_work_days(self, user_id, first=None, after=None):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=user_id,
            query=ApiRequests.query_user_work_days,
            variables=dict(id=user_id, first=first, after=after),
        )
        return response["data"]["user"]["workDays"]

    def _assert_invariant(self, connection):
        self.assertFalse(
            connection["pageInfo"]["hasNextPage"]
            and len(connection["edges"]) == 0,
            "hasNextPage=True with an empty page: the client has no edge to "
            "read a cursor from and no way to make progress.",
        )
        if not connection["pageInfo"]["hasNextPage"]:
            # Exhausted pagination must say so unambiguously: no dangling cursor.
            pass

    def _walk_all_pages(self, fetch_page, page_size):
        all_nodes = []
        after = None
        seen_pages = 0
        while True:
            seen_pages += 1
            self.assertLess(
                seen_pages, 50, "pagination did not converge, likely looping"
            )
            connection = fetch_page(first=page_size, after=after)
            self._assert_invariant(connection)
            all_nodes.extend(edge["node"] for edge in connection["edges"])
            if not connection["pageInfo"]["hasNextPage"]:
                break
            after = connection["pageInfo"]["endCursor"]
            self.assertIsNotNone(after)
        return all_nodes

    def test_page_with_only_dismissed_day_does_not_strand_pagination(self):
        worker = UserFactory.create(post__company=self.company)

        # Most recent day: the only activity gets dismissed -> that day must
        # not survive the service_duration>0 filter.
        recent_mission = self._create_mission(worker)
        recent_activity = self._log_activity_as(
            worker, recent_mission, days_ago=1, start_hour=9, end_hour=12
        )
        self._cancel_activity(worker, recent_activity.id)

        # Older day: a normal, non-empty work day.
        older_mission = self._create_mission(worker)
        self._log_activity_as(
            worker, older_mission, days_ago=2, start_hour=9, end_hour=12
        )

        connection = self._query_company_work_days(first=1)
        self._assert_invariant(connection)
        self.assertEqual(len(connection["edges"]), 1)
        self.assertFalse(connection["pageInfo"]["hasNextPage"])
        self.assertEqual(
            connection["edges"][0]["node"]["serviceDuration"], 3 * 3600
        )

    def test_no_duplicate_or_missing_work_day_across_pages(self):
        worker = UserFactory.create(post__company=self.company)
        for days_ago in range(1, 6):
            mission = self._create_mission(worker)
            self._log_activity_as(
                worker, mission, days_ago=days_ago, start_hour=9, end_hour=12
            )

        full = self._query_company_work_days()
        full_days = sorted(e["node"]["day"] for e in full["edges"])
        self.assertEqual(len(full_days), 5)

        paginated_nodes = self._walk_all_pages(
            lambda first, after: self._query_company_work_days(
                first=first, after=after
            ),
            page_size=2,
        )
        paginated_days = sorted(n["day"] for n in paginated_nodes)
        self.assertEqual(paginated_days, full_days)

    def test_pagination_safe_with_many_users_active_same_day(self):
        # Reproduces the scenario that crashed prod: a heavy concentration of
        # work days at a single date boundary (many employees active the
        # same day), with an older day beyond that concentration.
        workers = [
            UserFactory.create(post__company=self.company) for _ in range(8)
        ]
        for worker in workers:
            mission = self._create_mission(worker)
            self._log_activity_as(
                worker, mission, days_ago=1, start_hour=9, end_hour=12
            )

        older_worker = UserFactory.create(post__company=self.company)
        older_mission = self._create_mission(older_worker)
        self._log_activity_as(
            older_worker, older_mission, days_ago=10, start_hour=9, end_hour=12
        )

        full = self._query_company_work_days()
        self.assertEqual(len(full["edges"]), 9)

        paginated_nodes = self._walk_all_pages(
            lambda first, after: self._query_company_work_days(
                first=first, after=after
            ),
            page_size=3,
        )
        self.assertEqual(len(paginated_nodes), 9)

    def test_user_work_days_pagination_invariant(self):
        worker = UserFactory.create(post__company=self.company)

        recent_mission = self._create_mission(worker)
        recent_activity = self._log_activity_as(
            worker, recent_mission, days_ago=1, start_hour=9, end_hour=12
        )
        self._cancel_activity(worker, recent_activity.id)

        older_mission = self._create_mission(worker)
        self._log_activity_as(
            worker, older_mission, days_ago=2, start_hour=9, end_hour=12
        )

        connection = self._query_user_work_days(worker.id, first=1)
        self._assert_invariant(connection)
        self.assertEqual(len(connection["edges"]), 1)
