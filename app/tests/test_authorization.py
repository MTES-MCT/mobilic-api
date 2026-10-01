from datetime import datetime, timedelta, date
from unittest import TestCase, expectedFailure

from flask.ctx import AppContext
from freezegun import freeze_time
from graphql.type import (
    GraphQLNonNull,
    GraphQLList,
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
)

from app.controllers import graphql_schema, private_graphql_schema
from app.controllers.activity import LogActivity
from app.controllers.certificate import AddScenarioTestingResult
from app.controllers.expenditure import LogExpenditure
from app.controllers.location_entry import LogMissionLocation
from app.controllers.notification_campaign import CreateNotificationCampaign
from app.controllers.user import ChangeGender, DisableWarning
from app.controllers.user_survey_actions import CreateSurveyAction
from app.domain.log_activities import log_activity
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import check_company_id_against_scope
from app.models import Mission
from app.models.activity import ActivityType
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
    test_post_graphql,
    test_post_graphql_unexposed,
)
from app.tests.helpers import ApiRequests, make_authenticated_request
from app import app, db
from app.helpers.errors import AuthorizationError
from app.domain.permissions import (
    company_admin,
    is_employed_by_company_over_period,
    can_actor_read_mission,
    check_actor_can_write_on_mission_over_period,
)
from app.seed import UserFactory, CompanyFactory


class TestAuthorization(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.departed_admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
            post__start_date=date(2019, 1, 1),
            post__end_date=date(2020, 1, 1),
        )
        self.team_leader = UserFactory.create(post__company=self.company)
        self.workers = [
            UserFactory.create(post__company=self.company) for u in range(0, 3)
        ]
        self.departed_worker = UserFactory.create(
            post__company=self.company,
            post__start_date=date(2019, 1, 1),
            post__end_date=date(2020, 1, 1),
        )
        self.current_user = self.team_leader
        self._app_context = AppContext(app)
        self.current_user_context = AuthenticatedUserContext(
            user=self.current_user
        )
        self._app_context.__enter__()
        self.current_user_context.__enter__()

    def tearDown(self):
        self.current_user_context.__exit__(None, None, None)
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _create_mission(self):
        return Mission.create(
            submitter=self.team_leader,
            reception_time=datetime.now(),
            company=self.company,
        )

    def test_is_company_admin(self):
        self.assertEqual(company_admin(self.admin, self.company), True)
        self.assertEqual(company_admin(self.admin, self.company.id), True)

        with freeze_time(date(2019, 6, 1)):
            self.assertEqual(company_admin(self.admin, self.company), True)
            self.assertEqual(company_admin(self.admin, self.company.id), True)

            self.assertEqual(
                company_admin(self.departed_admin, self.company), True
            )
            self.assertEqual(
                company_admin(self.departed_admin, self.company.id), True
            )

        with freeze_time(date(2020, 6, 1)):
            self.assertEqual(company_admin(self.admin, self.company), True)
            self.assertEqual(company_admin(self.admin, self.company.id), True)

            self.assertEqual(
                company_admin(self.departed_admin, self.company), False
            )
            self.assertEqual(
                company_admin(self.departed_admin, self.company.id), False
            )

    def test_is_employed_by_company_over_period(self):
        for start_date, end_date in [
            (date(2019, 1, 1), date(2019, 2, 2)),
            (date(2019, 6, 1), date(2019, 7, 2)),
            (date(2019, 1, 1), date(2020, 1, 1)),
        ]:
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.admin, self.company, start=start_date, end=end_date
                ),
                True,
            )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.team_leader,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )
            for worker in self.workers:
                self.assertEqual(
                    is_employed_by_company_over_period(
                        worker, self.company, start=start_date, end=end_date
                    ),
                    True,
                )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.departed_worker,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )

        for start_date, end_date in [
            (date(2018, 1, 1), date(2018, 2, 2)),
            (date(2019, 6, 1), date(2020, 1, 2)),
            (date(2018, 1, 1), date(2021, 1, 1)),
        ]:
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.admin, self.company, start=start_date, end=end_date
                ),
                True,
            )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.team_leader,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )
            for worker in self.workers:
                self.assertEqual(
                    is_employed_by_company_over_period(
                        worker, self.company, start=start_date, end=end_date
                    ),
                    True,
                )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.departed_worker,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                False,
            )

    def test_can_actor_access_mission(self):
        mission = self._create_mission()

        self.assertEqual(can_actor_read_mission(self.admin, mission), True)
        self.assertEqual(
            can_actor_read_mission(self.team_leader, mission), True
        )
        for w in self.workers:
            self.assertEqual(can_actor_read_mission(w, mission), False)

        with freeze_time(date(2019, 6, 1)):
            self.assertEqual(
                can_actor_read_mission(self.departed_admin, mission), True
            )

        with freeze_time(date(2020, 6, 1)):
            self.assertEqual(
                can_actor_read_mission(self.departed_admin, mission), False
            )

        log_activity(
            submitter=self.team_leader,
            user=self.workers[0],
            mission=mission,
            type=ActivityType.WORK,
            switch_mode=True,
            reception_time=datetime.now(),
            start_time=datetime.now(),
        )
        self.assertEqual(can_actor_read_mission(self.admin, mission), True)
        self.assertEqual(
            can_actor_read_mission(self.team_leader, mission), True
        )
        for w in self.workers:
            self.assertEqual(
                can_actor_read_mission(w, mission), w == self.workers[0]
            )

    def test_can_actor_write_on_mission(self):
        mission = self._create_mission()

        check_actor_can_write_on_mission_over_period(self.admin, mission)
        check_actor_can_write_on_mission_over_period(self.team_leader, mission)

        for w in self.workers:
            with self.assertRaises(AuthorizationError):
                check_actor_can_write_on_mission_over_period(w, mission),

    def test_check_company_id_against_scope(self):

        # current admin ok
        with AuthenticatedUserContext(self.admin):
            check_company_id_against_scope(self.company.id)

        # departed admin -> authorizationError
        with AuthenticatedUserContext(self.departed_admin):
            with self.assertRaises(AuthorizationError):
                check_company_id_against_scope(self.company.id)


class TestAuthorizationErrorLeak(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.user = UserFactory.create(post__company=self.company)

    @expectedFailure
    def test_log_activity_on_missing_mission_does_not_leak_python_error(self):
        """AE2 [Medium] with_authorization_policy leaks a raw AttributeError/NoneType on a non-existent target."""
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.user.id,
            query=ApiRequests.log_activity,
            variables={
                "type": ActivityType.WORK,
                "start_time": datetime(2023, 1, 1, 8),
                "mission_id": 99999999,
            },
        )
        errors = response.get("errors") or []
        self.assertTrue(
            errors, "A non-existent mission_id should produce an error"
        )
        messages = " ".join(e.get("message", "") for e in errors)
        self.assertNotIn(
            "NoneType",
            messages,
            f"Raw Python error leaked to the client: {messages}",
        )
        self.assertNotIn(
            "AttributeError",
            messages,
            f"Raw Python error leaked to the client: {messages}",
        )


AUTH_ERROR_CODES = {
    "AUTHENTICATION_ERROR",
    "AUTHORIZATION_ERROR",
    "INVALID_TOKEN",
    "EXPIRED_TOKEN",
    "BLOCKED_ACCOUNT_ERROR",
}

PUBLIC_ENDPOINTS = {
    "public:mutation.auth.login",
    "private:mutation.auth.franceConnectLogin",
    "private:mutation.auth.agentConnectLogin",
    "private:mutation.account.requestResetPassword",
    "private:mutation.signUp.user",
}

_SCALAR_LITERALS = {
    "Int": "1",
    "Float": "1.0",
    "String": '"x"',
    "Boolean": "false",
    "ID": '"1"',
    "Date": '"2020-01-01"',
    "DateTime": '"2020-01-01T00:00:00"',
    "TimeStamp": "1577836800",
    "Email": '"a@b.co"',
    "Password": '"Passw0rd!23"',
    "GenericScalar": '"x"',
}


def _unwrap(gql_type):
    while isinstance(gql_type, (GraphQLNonNull, GraphQLList)):
        gql_type = gql_type.of_type
    return gql_type


def _literal(gql_type):
    if isinstance(gql_type, GraphQLNonNull):
        return _literal(gql_type.of_type)
    if isinstance(gql_type, GraphQLList):
        return "[]"
    if isinstance(gql_type, GraphQLEnumType):
        return next(iter(gql_type.values.keys()))
    if isinstance(gql_type, GraphQLInputObjectType):
        parts = [
            f"{name}: {_literal(f.type)}"
            for name, f in gql_type.fields.items()
            if isinstance(f.type, GraphQLNonNull)
        ]
        return "{" + ", ".join(parts) + "}"
    name = getattr(gql_type, "name", None)
    if name in _SCALAR_LITERALS:
        return _SCALAR_LITERALS[name]
    raise NotImplementedError(name)


def _required_args(args):
    parts = [
        f"{name}: {_literal(arg.type)}"
        for name, arg in args.items()
        if isinstance(arg.type, GraphQLNonNull)
    ]
    return f"({', '.join(parts)})" if parts else ""


def _selection(return_type):
    if isinstance(
        _unwrap(return_type),
        (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType),
    ):
        return " { __typename }"
    return ""


def _is_group(field):
    return (
        not field.args
        and isinstance(_unwrap(field.type), GraphQLObjectType)
        and bool(_unwrap(field.type).fields)
    )


def _endpoints(schema):
    for name, field in schema.get_query_type().fields.items():
        yield f"query.{name}", "query", None, name, field

    mutation_type = schema.get_mutation_type()
    if not mutation_type:
        return
    for gname, gfield in mutation_type.fields.items():
        if _is_group(gfield):
            for lname, lfield in _unwrap(gfield.type).fields.items():
                yield (
                    f"mutation.{gname}.{lname}",
                    "mutation",
                    gname,
                    lname,
                    lfield,
                )
        else:
            yield f"mutation.{gname}", "mutation", None, gname, gfield


def _document(kind, group, name, field):
    args = _required_args(field.args)
    sel = _selection(field.type)
    if kind == "query":
        return f"query {{ {name}{args}{sel} }}"
    if group:
        return f"mutation {{ {group} {{ {name}{args}{sel} }} }}"
    return f"mutation {{ {name}{args}{sel} }}"


class TestEndpointAuthCoverage(BaseTest):
    def _check_schema(self, label, schema, poster):
        violations, untestable = [], []
        for path, kind, group, name, field in _endpoints(schema):
            key = f"{label}:{path}"
            try:
                document = _document(kind, group, name, field)
            except NotImplementedError as exc:
                untestable.append((key, f"unsupported arg type {exc}"))
                continue
            response = poster(document).json
            errors = response.get("errors") or []
            codes = [(e.get("extensions") or {}).get("code") for e in errors]
            if any(code in AUTH_ERROR_CODES for code in codes):
                continue
            if key in PUBLIC_ENDPOINTS:
                continue
            if response.get("data") or any(codes):
                violations.append((key, codes))
            else:
                untestable.append((key, "only validation errors"))
        return violations, untestable

    @expectedFailure
    def test_all_endpoints_reject_unauthenticated_access(self):
        all_violations, all_untestable = [], []
        for label, schema, poster in [
            ("public", graphql_schema, test_post_graphql),
            ("private", private_graphql_schema, test_post_graphql_unexposed),
        ]:
            violations, untestable = self._check_schema(label, schema, poster)
            all_violations += violations
            all_untestable += untestable

        self.assertEqual(
            all_violations,
            [],
            msg=(
                "Endpoints reachable without authentication and not in "
                f"PUBLIC_ENDPOINTS: {all_violations}"
            ),
        )


ENUM_BLOCKED_MUTATIONS = [
    LogActivity,
    LogExpenditure,
    LogMissionLocation,
    ChangeGender,
    DisableWarning,
    AddScenarioTestingResult,
    CreateSurveyAction,
    CreateNotificationCampaign,
]


class TestEnumBlockedMutationsRequireAuth(TestCase):
    def test_mutations_uncovered_by_introspective_loop_require_auth(self):
        """Structural guard for the 8 mutations the generic auth-coverage loop
        cannot exercise (Graphene 2 scalar enums): each must inherit
        AuthenticatedMutation."""
        for mutation in ENUM_BLOCKED_MUTATIONS:
            with self.subTest(mutation=mutation.__name__):
                self.assertTrue(
                    issubclass(mutation, AuthenticatedMutation),
                    f"{mutation.__name__} is reachable without authentication",
                )
