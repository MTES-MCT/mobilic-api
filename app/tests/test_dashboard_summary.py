from datetime import datetime, date, time, timezone, timedelta
from unittest.mock import patch, MagicMock

from app import db
from app.domain.dashboard_summary import (
    PENDING_VALIDATIONS_CACHE_TTL,
    _count_pending_validations,
    _pending_validations_cache_key,
    invalidate_pending_validations_cache,
)
from app.domain.mission import end_mission_for_user
from app.models.activity import ActivityType
from app.models import MissionEnd, MissionValidation
from app.models.employment import (
    Employment,
    EmploymentRequestValidationStatus,
)
from app.seed import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.factories import ActivityFactory, MissionFactory, TeamFactory
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import init_regulation_checks_data, init_businesses_data


EDIT_ACTIVITY_MUTATION = """
    mutation ($activityId: Int!, $startTime: TimeStamp) {
        activities {
            editActivity (activityId: $activityId, startTime: $startTime) {
                id
            }
        }
    }
"""

CANCEL_MISSION_MUTATION = """
    mutation ($missionId: Int!, $userId: Int!) {
        activities {
            cancelMission (missionId: $missionId, userId: $userId) {
                id
            }
        }
    }
"""

DASHBOARD_SUMMARY_QUERY = """
    query ($id: Int!) {
        company(id: $id) {
            dashboardSummary {
                activeMissionsCount
                pendingValidationsCount
                pendingInvitationsCount
                inactiveEmployeesCount
                autoValidatedMissionsCount
                hasAnyMissionThisWeek
            }
        }
    }
"""


class TestDashboardSummary(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.employee = UserFactory.create(
            post__company=self.company,
        )
        self.now = datetime.now(tz=timezone.utc)

    def _query(self, user=None):
        return test_post_graphql(
            DASHBOARD_SUMMARY_QUERY,
            mock_authentication_with_user=user or self.admin,
            variables=dict(id=self.company.id),
        )

    def _get_summary(self, response):
        return response.json["data"]["company"]["dashboardSummary"]

    def _create_mission_with_activity(self, user=None, end_time=None):
        user = user or self.employee
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=user.id,
            reception_time=self.now,
        )
        last_update = end_time + timedelta(minutes=1) if end_time else self.now
        ActivityFactory.create(
            mission=mission,
            user=user,
            submitter=user,
            type=ActivityType.DRIVE,
            reception_time=self.now,
            start_time=self.now,
            end_time=end_time,
            last_update_time=last_update,
        )
        return mission

    def _end_mission(self, mission, user=None):
        user = user or self.employee
        db.session.add(
            MissionEnd(
                submitter=user,
                reception_time=self.now,
                user=user,
                mission=mission,
            )
        )
        db.session.commit()

    def _validate_mission(self, mission, is_auto=False, user=None):
        db.session.add(
            MissionValidation(
                submitter=self.admin if not is_auto else None,
                mission=mission,
                user=user,
                reception_time=self.now,
                is_admin=True,
                is_auto=is_auto,
            )
        )
        db.session.commit()

    def _worker_validate_mission(self, mission, user=None):
        user = user or self.employee
        db.session.add(
            MissionValidation(
                submitter=user,
                mission=mission,
                user=user,
                reception_time=self.now,
                is_admin=False,
                is_auto=False,
            )
        )
        db.session.commit()

    def _create_pending_mission_for_users(self, users):
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=users[0].id,
            reception_time=self.now,
        )
        for user in users:
            ActivityFactory.create(
                mission=mission,
                user=user,
                submitter=user,
                type=ActivityType.DRIVE,
                reception_time=self.now,
                start_time=self.now,
                end_time=self.now + timedelta(minutes=1),
                last_update_time=self.now + timedelta(minutes=2),
            )
            self._end_mission(mission, user)
        self._worker_validate_mission(mission, users[0])
        return mission

    def test_empty_dashboard(self):
        response = self._query()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json.get("errors"))
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 0)
        self.assertEqual(data["pendingValidationsCount"], 0)
        self.assertEqual(data["pendingInvitationsCount"], 0)
        # employee never active and no activity today → counted as inactive
        self.assertEqual(data["inactiveEmployeesCount"], 1)
        self.assertEqual(data["autoValidatedMissionsCount"], 0)
        self.assertFalse(data["hasAnyMissionThisWeek"])

    def test_has_any_mission_this_week_true(self):
        self._create_mission_with_activity()
        response = self._query()
        data = self._get_summary(response)
        self.assertTrue(data["hasAnyMissionThisWeek"])

    def test_has_any_mission_this_week_false_when_only_old(self):
        """Activities older than the current week do not count.

        Use a 60-day offset so the test stays stable regardless of the
        weekday it runs on (a 30-day offset can still fall in the same
        ISO week when today is a Monday)."""
        old_time = self.now - timedelta(days=60)
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=old_time,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=old_time,
            start_time=old_time,
            last_update_time=old_time,
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertFalse(data["hasAnyMissionThisWeek"])

    def _set_last_active_at(self, user, days_ago):
        from app.models import Employment

        employment = (
            db.session.query(Employment)
            .filter(
                Employment.company_id == self.company.id,
                Employment.user_id == user.id,
            )
            .one()
        )
        employment.last_active_at = self.now - timedelta(days=days_ago)
        db.session.commit()

    def test_inactive_employee_never_active_counted(self):
        """last_active_at is None (never used Mobilic) and no Activity
        today → counted as inactive."""
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["inactiveEmployeesCount"], 1)

    def test_inactive_employee_active_recently(self):
        """Active in last 30 days but not today → counted as inactive."""
        self._set_last_active_at(self.employee, days_ago=5)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["inactiveEmployeesCount"], 1)

    def test_inactive_employee_long_gone_not_counted(self):
        """Last activity older than 30 days → not counted (out of window)."""
        self._set_last_active_at(self.employee, days_ago=45)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["inactiveEmployeesCount"], 0)

    def test_inactive_employee_last_active_today_no_activity_counted(self):
        """last_active_at today but no Activity today → counted as inactive
        (aligned with the InactiveEmployeesDropdown which only excludes
        users that have a workDay for today)."""
        self._set_last_active_at(self.employee, days_ago=0)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["inactiveEmployeesCount"], 1)

    def test_inactive_employee_with_activity_today_excluded(self):
        """Activity today excludes the user from the count even when
        last_active_at also falls today."""
        self._set_last_active_at(self.employee, days_ago=0)
        self._create_mission_with_activity(user=self.employee)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["inactiveEmployeesCount"], 0)

    def test_running_activity_counts_as_active(self):
        self._create_mission_with_activity()
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 1)

    def test_long_running_activity_not_counted_as_active(self):
        """An activity left open for more than the active-missions window
        (data quality bug) is excluded from the counter, so Postgres can
        use the start_time range filter instead of scanning the full
        activity history of the company."""
        old_time = self.now - timedelta(days=60)
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=old_time,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=old_time,
            start_time=old_time,
            last_update_time=old_time,
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 0)

    def test_closed_activity_not_active(self):
        """Mission whose activities all have an end_time set is not active,
        even if no MissionEnd has been recorded yet (worker still needs
        to validate, but the chronometer is no longer ticking)."""
        self._create_mission_with_activity(
            end_time=self.now + timedelta(hours=1)
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 0)

    def test_mission_active_when_one_user_still_running(self):
        """Mission where user A has closed her activity but user B is
        still on the road must remain counted as active."""
        mission = self._create_mission_with_activity(
            end_time=self.now + timedelta(hours=1)
        )
        other = UserFactory.create(post__company=self.company)
        ActivityFactory.create(
            mission=mission,
            user=other,
            submitter=other,
            type=ActivityType.DRIVE,
            reception_time=self.now,
            start_time=self.now,
            last_update_time=self.now,
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 1)

    def test_pending_validations_count(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._worker_validate_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 1)

    def test_pending_team_mission_visible_if_actor_administers_one_team(self):
        """An administered-team participant makes the whole mission visible,
        even when another participant belongs to a team the actor does not
        administer."""
        administered_team = TeamFactory.create(company=self.company)
        other_team = TeamFactory.create(company=self.company)
        administered_team.admin_users.append(self.admin)
        db.session.query(Employment).filter_by(
            company_id=self.company.id,
            user_id=self.employee.id,
        ).one().team = administered_team
        other_employee = UserFactory.create(
            post__company=self.company,
            post__team=other_team,
        )
        db.session.commit()

        self._create_pending_mission_for_users([self.employee, other_employee])

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 1)

    def test_pending_team_mission_hidden_if_actor_administers_no_team(self):
        """A mission with only participants in non-administered teams stays
        outside the actor's dashboard scope."""
        other_team = TeamFactory.create(company=self.company)
        other_employee = UserFactory.create(
            post__company=self.company,
            post__team=other_team,
        )
        self._create_pending_mission_for_users([other_employee])

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_pending_team_mission_visible_if_teamless_participant(self):
        """A teamless participant makes the whole mission visible, even when
        another participant belongs to a team the actor does not
        administer and the actor administers no team at all."""
        other_team = TeamFactory.create(company=self.company)
        other_employee = UserFactory.create(
            post__company=self.company,
            post__team=other_team,
        )
        # self.employee has no team (set up in setUp)
        self._create_pending_mission_for_users([self.employee, other_employee])

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 1)

    def test_pending_team_mission_hidden_if_only_invisible_participant_validated(
        self,
    ):
        """A visible (teamless) participant makes the mission visible, but it
        must not count until that visible participant - not just some other,
        invisible participant - has actually validated it."""
        other_team = TeamFactory.create(company=self.company)
        other_employee = UserFactory.create(
            post__company=self.company,
            post__team=other_team,
        )
        # Only other_employee (invisible to the actor) validates; self.employee
        # (teamless, visible) does not.
        self._create_pending_mission_for_users([other_employee, self.employee])

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_pending_counts_stale_running_mission_of_visible_participant(self):
        """A mission still running (no MissionEnd, no worker validation) must
        still count once a visible participant's activity has been running
        for more than 24h - mirrors the front's missionNotUpdatedForTooLong
        bypass (common/utils/mission.js)."""
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=self.now,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=self.now - timedelta(hours=25),
            start_time=self.now - timedelta(hours=25),
            end_time=None,
            last_update_time=self.now - timedelta(hours=25),
        )

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 1)

    def test_pending_ignores_running_mission_under_24h(self):
        """A mission still running for less than 24h must not count, since
        it is neither ended/worker-validated nor stale enough for the
        bypass."""
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=self.now,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=self.now - timedelta(hours=1),
            start_time=self.now - timedelta(hours=1),
            end_time=None,
            last_update_time=self.now - timedelta(hours=1),
        )

        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_pending_validations_count_ignores_old_missions(self):
        """Missions older than the loaded window are not counted, even if
        technically waiting for an admin validation."""
        old_time = self.now - timedelta(days=60)
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=old_time,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=old_time,
            start_time=old_time,
            last_update_time=old_time,
        )
        self._end_mission(mission)
        self._worker_validate_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_ended_mission_without_worker_validation_not_pending(self):
        """Mission terminée mais pas encore validée par le salarié → ne compte pas."""
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_validated_mission_not_pending(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._worker_validate_mission(mission)
        self._validate_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_pending_invitations_count(self):
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=None,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            email="invite@test.com",
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingInvitationsCount"], 1)

    def test_pending_invitations_count_includes_invited_existing_user(self):
        """Pending employments attached to an already-registered Mobilic
        user must also be reported (e.g. invitation by user ID)."""
        invited = UserFactory.create()
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=invited,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            email=invited.email,
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingInvitationsCount"], 1)

    def test_inactive_employees_with_activity(self):
        self._create_mission_with_activity(user=self.employee)
        response = self._query()
        data = self._get_summary(response)
        # employee has activity today → 0 inactive (admin excluded from count)
        self.assertEqual(data["inactiveEmployeesCount"], 0)

    def test_auto_validated_missions_count(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._validate_mission(mission, is_auto=True, user=self.employee)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["autoValidatedMissionsCount"], 1)
        # auto-validated = not pending
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_auto_validated_yesterday_not_counted(self):
        """Auto-validations older than today are excluded from the counter."""
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._validate_mission(mission, is_auto=True, user=self.employee)
        validation = db.session.query(MissionValidation).first()
        validation.creation_time = self.now - timedelta(days=1)
        db.session.commit()
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["autoValidatedMissionsCount"], 0)

    def test_non_admin_cannot_access(self):
        other_user = UserFactory.create()
        response = self._query(user=other_user)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json.get("errors"))


class TestPendingValidationsCache(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.actor_user_id = 1

    @patch("app.domain.dashboard_summary.get_redis_client")
    def test_cache_hit_returns_cached_value(self, mock_redis_factory):
        mock_redis_factory.return_value = MagicMock(get=lambda k: b"42")
        self.assertEqual(
            _count_pending_validations(self.company.id, self.actor_user_id),
            42,
        )

    @patch("app.domain.dashboard_summary.get_redis_client")
    def test_cache_miss_computes_and_stores(self, mock_redis_factory):
        store = {}
        mock_redis_factory.return_value = MagicMock(
            get=lambda k: None,
            setex=lambda k, t, v: store.__setitem__(k, (t, v)),
        )
        result = _count_pending_validations(
            self.company.id, self.actor_user_id
        )
        key = _pending_validations_cache_key(
            self.company.id, self.actor_user_id
        )
        self.assertIn(key, store)
        self.assertEqual(store[key], (PENDING_VALIDATIONS_CACHE_TTL, result))

    @patch("app.domain.dashboard_summary.get_redis_client")
    def test_redis_down_falls_back_to_sql(self, mock_redis_factory):
        mock_redis_factory.side_effect = Exception("Redis connection failed")
        # empty company → 0, must not raise
        self.assertEqual(
            _count_pending_validations(self.company.id, self.actor_user_id),
            0,
        )

    @patch("app.domain.dashboard_summary.get_redis_client")
    def test_invalidation_bumps_cache_version(self, mock_redis_factory):
        incremented = []
        mock_redis_factory.return_value = MagicMock(
            incr=lambda k: incremented.append(k),
        )
        invalidate_pending_validations_cache(self.company.id)
        self.assertEqual(
            incremented,
            [f"dashboard:pending_validations:version:{self.company.id}"],
        )

    @patch("app.domain.mission.invalidate_pending_validations_cache")
    def test_end_mission_invalidates_cache(self, mock_invalidate):
        user = UserFactory.create(
            post__company=self.company, post__has_admin_rights=False
        )
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=user.id,
            reception_time=datetime.now(),
        )
        end_mission_for_user(user=user, mission=mission)
        mock_invalidate.assert_called_once_with(self.company.id)

    @patch("app.controllers.activity.invalidate_pending_validations_cache")
    def test_edit_activity_invalidates_cache(self, mock_invalidate):
        user = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        now = datetime.now()
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=user.id,
            reception_time=now,
        )
        activity = ActivityFactory.create(
            mission=mission,
            user=user,
            submitter=user,
            type=ActivityType.DRIVE,
            reception_time=now,
            start_time=now,
            end_time=None,
            last_update_time=now,
        )
        response = test_post_graphql(
            EDIT_ACTIVITY_MUTATION,
            mock_authentication_with_user=user,
            variables=dict(
                activityId=activity.id,
                startTime=int((now - timedelta(hours=1)).timestamp()),
            ),
        )
        self.assertIsNone(response.json.get("errors"))
        mock_invalidate.assert_called_once_with(self.company.id)

    @patch("app.controllers.mission.invalidate_pending_validations_cache")
    def test_cancel_mission_invalidates_cache(self, mock_invalidate):
        init_regulation_checks_data()
        init_businesses_data()
        user = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        now = datetime.now()
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=user.id,
            reception_time=now,
        )
        ActivityFactory.create(
            mission=mission,
            user=user,
            submitter=user,
            type=ActivityType.DRIVE,
            reception_time=now,
            start_time=now,
            end_time=None,
            last_update_time=now,
        )
        response = test_post_graphql(
            CANCEL_MISSION_MUTATION,
            mock_authentication_with_user=user,
            variables=dict(missionId=mission.id, userId=user.id),
        )
        self.assertIsNone(response.json.get("errors"))
        mock_invalidate.assert_called_once_with(self.company.id)
