from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app import db
from app.data_access.control_data import ControllerControlOutput
from app.models.technical_incident import (
    TechnicalIncident,
    TechnicalIncidentType,
    TechnicalIncidentCategory,
    TechnicalIncidentNature,
)
from app.seed.factories import (
    UserFactory,
    CompanyFactory,
    ControllerUserFactory,
)
from app.tests import BaseTest, test_post_graphql_unexposed

CREATE_INCIDENT = """
    mutation ($technicalType: TechnicalIncidentTypeEnum!,
              $startTime: TimeStamp!, $endTime: TimeStamp,
              $description: String) {
        technicalIncidents {
            createTechnicalIncident(
                technicalType: $technicalType, startTime: $startTime,
                endTime: $endTime, description: $description
            ) { id technicalType nature isOngoing }
        }
    }
"""

UPDATE_INCIDENT = """
    mutation ($incidentId: Int!,
              $technicalType: TechnicalIncidentTypeEnum,
              $description: String, $endTime: TimeStamp, $reopen: Boolean) {
        technicalIncidents {
            updateTechnicalIncident(
                incidentId: $incidentId, technicalType: $technicalType,
                description: $description, endTime: $endTime, reopen: $reopen
            ) { id technicalType nature description endTime isOngoing }
        }
    }
"""

READ_INCIDENTS = """
    query {
        technicalIncidents { id technicalType nature isOngoing }
    }
"""

READ_INCIDENTS_WITH_DESCRIPTION = """
    query {
        technicalIncidents { id nature description }
    }
"""


class TestTechnicalIncidentModel(BaseTest):
    def test_every_type_derives_category_and_nature(self):
        for incident_type in TechnicalIncidentType:
            incident = TechnicalIncident(
                technical_type=incident_type,
                start_time=datetime.utcnow(),
            )
            self.assertIsInstance(incident.category, TechnicalIncidentCategory)
            self.assertIsInstance(incident.nature, TechnicalIncidentNature)

    def test_derived_mappings_spot_check(self):
        cases = {
            TechnicalIncidentType.SERVER_DOWN: (
                TechnicalIncidentCategory.INFRASTRUCTURE,
                TechnicalIncidentNature.PLATFORM_UNAVAILABLE,
            ),
            TechnicalIncidentType.SSL_EXPIRED: (
                TechnicalIncidentCategory.INFRASTRUCTURE,
                TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
            ),
            TechnicalIncidentType.TIME_ENTRY_BUG: (
                TechnicalIncidentCategory.APPLICATIVE,
                TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
            ),
            TechnicalIncidentType.AUTH_OUTAGE: (
                TechnicalIncidentCategory.ACCESS_EXTERNAL,
                TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
            ),
            TechnicalIncidentType.PLANNED_MAINTENANCE: (
                TechnicalIncidentCategory.SPECIAL_CASE,
                TechnicalIncidentNature.PLANNED_MAINTENANCE,
            ),
        }
        for incident_type, (category, nature) in cases.items():
            incident = TechnicalIncident(
                technical_type=incident_type,
                start_time=datetime.utcnow(),
            )
            self.assertEqual(incident.category, category)
            self.assertEqual(incident.nature, nature)

    def test_ongoing_incident_stays_visible_without_end(self):
        recent = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime.utcnow() - timedelta(hours=2),
        )
        self.assertTrue(recent.is_ongoing)
        # Effective end is capped at start + visible window, never persisted.
        self.assertEqual(
            recent.effective_end_time,
            recent.start_time + timedelta(hours=48),
        )

        old = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime.utcnow() - timedelta(hours=60),
        )
        # Past the visible window it is no longer shown as ongoing, without
        # writing any fabricated end_time in the database.
        self.assertFalse(old.is_ongoing)
        self.assertIsNone(old.end_time)
        self.assertEqual(
            old.effective_end_time,
            old.start_time + timedelta(hours=48),
        )


class TestTechnicalIncidentApi(BaseTest):
    def setUp(self):
        super().setUp()
        # Backfill migration seeds incidents: start from an empty table.
        TechnicalIncident.query.delete()
        self.bizdev = UserFactory.create(bizdev=True)
        self.company = CompanyFactory.create()
        self.worker = UserFactory.create(post__company=self.company)
        db.session.commit()

    def _create_variables(self, end_time=None):
        return {
            "technicalType": "ssl_expired",
            "startTime": int(datetime(2026, 1, 27, 8, 40).timestamp()),
            "endTime": end_time,
            "description": "Certificat expiré",
        }

    def test_bizdev_can_create_and_query(self):
        resp = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        self.assertIsNone(resp.json.get("errors"))
        created = resp.json["data"]["technicalIncidents"][
            "createTechnicalIncident"
        ]
        self.assertEqual(created["nature"], "login_impossible")

        read = test_post_graphql_unexposed(
            READ_INCIDENTS,
            mock_authentication_with_user=self.bizdev,
        )
        incidents = read.json["data"]["technicalIncidents"]
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["nature"], "login_impossible")

    def test_worker_cannot_create(self):
        resp = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.worker,
            variables=self._create_variables(),
        )
        self.assertIsNotNone(resp.json.get("errors"))
        self.assertEqual(TechnicalIncident.query.count(), 0)

    def test_bizdev_can_update(self):
        create = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        incident_id = create.json["data"]["technicalIncidents"][
            "createTechnicalIncident"
        ]["id"]

        resp = test_post_graphql_unexposed(
            UPDATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables={
                "incidentId": int(incident_id),
                "technicalType": "auth_outage",
                "description": "Panne SSO",
            },
        )
        self.assertIsNone(resp.json.get("errors"))
        updated = resp.json["data"]["technicalIncidents"][
            "updateTechnicalIncident"
        ]
        self.assertEqual(updated["technicalType"], "auth_outage")
        self.assertEqual(updated["description"], "Panne SSO")

    def test_controller_can_read(self):
        test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        controller = ControllerUserFactory.create()
        db.session.commit()

        read = test_post_graphql_unexposed(
            READ_INCIDENTS,
            mock_authentication_with_user=controller,
        )
        self.assertIsNone(read.json.get("errors"))
        self.assertEqual(len(read.json["data"]["technicalIncidents"]), 1)

    def test_description_hidden_from_controller(self):
        test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        controller = ControllerUserFactory.create()
        db.session.commit()

        as_bizdev = test_post_graphql_unexposed(
            READ_INCIDENTS_WITH_DESCRIPTION,
            mock_authentication_with_user=self.bizdev,
        )
        self.assertEqual(
            as_bizdev.json["data"]["technicalIncidents"][0]["description"],
            "Certificat expiré",
        )

        as_controller = test_post_graphql_unexposed(
            READ_INCIDENTS_WITH_DESCRIPTION,
            mock_authentication_with_user=controller,
        )
        self.assertIsNone(as_controller.json.get("errors"))
        self.assertIsNone(
            as_controller.json["data"]["technicalIncidents"][0]["description"]
        )

    def test_too_long_description_rejected(self):
        variables = self._create_variables()
        variables["description"] = "x" * 2001
        resp = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=variables,
        )
        self.assertIsNotNone(resp.json.get("errors"))
        self.assertEqual(TechnicalIncident.query.count(), 0)

    def test_update_can_close_and_reopen_incident(self):
        create = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        incident_id = create.json["data"]["technicalIncidents"][
            "createTechnicalIncident"
        ]["id"]

        close = test_post_graphql_unexposed(
            UPDATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables={
                "incidentId": int(incident_id),
                "endTime": int(datetime(2026, 1, 27, 10, 0).timestamp()),
            },
        )
        self.assertIsNone(close.json.get("errors"))
        closed = close.json["data"]["technicalIncidents"][
            "updateTechnicalIncident"
        ]
        self.assertIsNotNone(closed["endTime"])
        self.assertFalse(closed["isOngoing"])

        reopen = test_post_graphql_unexposed(
            UPDATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables={"incidentId": int(incident_id), "reopen": True},
        )
        self.assertIsNone(reopen.json.get("errors"))
        reopened = reopen.json["data"]["technicalIncidents"][
            "updateTechnicalIncident"
        ]
        self.assertIsNone(reopened["endTime"])
        incident = TechnicalIncident.query.get(int(incident_id))
        self.assertIsNone(incident.end_time)

    def test_update_cannot_reopen_and_close_at_once(self):
        create = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        incident_id = create.json["data"]["technicalIncidents"][
            "createTechnicalIncident"
        ]["id"]

        resp = test_post_graphql_unexposed(
            UPDATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables={
                "incidentId": int(incident_id),
                "endTime": int(datetime(2026, 1, 27, 10, 0).timestamp()),
                "reopen": True,
            },
        )
        self.assertIsNotNone(resp.json.get("errors"))


class TestControlDataTechnicalIncidents(BaseTest):
    def setUp(self):
        super().setUp()
        TechnicalIncident.query.delete()
        self.in_period = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime(2026, 1, 27, 8, 0),
            end_time=datetime(2026, 1, 27, 12, 0),
        )
        self.out_of_period = TechnicalIncident(
            technical_type=TechnicalIncidentType.DNS_SWITCH,
            start_time=datetime(2026, 3, 1, 8, 0),
            end_time=datetime(2026, 3, 1, 12, 0),
        )
        db.session.add_all([self.in_period, self.out_of_period])
        db.session.commit()

    def _resolve(self, start_date, end_date):
        control = SimpleNamespace(
            history_start_date=start_date, history_end_date=end_date
        )
        return ControllerControlOutput.resolve_technical_incidents(
            control, None
        )

    def test_only_incidents_overlapping_period_are_returned(self):
        result = self._resolve(date(2026, 1, 26), date(2026, 1, 28))
        self.assertEqual([i.id for i in result], [self.in_period.id])

    def test_no_period_returns_empty(self):
        self.assertEqual(self._resolve(None, None), [])

    def test_open_incident_visible_only_within_capped_window(self):
        open_incident = TechnicalIncident(
            technical_type=TechnicalIncidentType.AUTH_OUTAGE,
            start_time=datetime(2026, 2, 1, 8, 0),
        )
        db.session.add(open_incident)
        db.session.commit()
        # Within the 48h cap: visible.
        within = self._resolve(date(2026, 2, 2), date(2026, 2, 2))
        self.assertIn(open_incident.id, [i.id for i in within])
        # Beyond the 48h cap: no longer returned, without any persisted end.
        beyond = self._resolve(date(2026, 2, 5), date(2026, 2, 5))
        self.assertNotIn(open_incident.id, [i.id for i in beyond])
        self.assertIsNone(open_incident.end_time)
