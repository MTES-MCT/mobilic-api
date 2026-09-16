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
            ) { id technicalType category nature isOngoing }
        }
    }
"""

RESOLVE_INCIDENT = """
    mutation ($incidentId: Int!, $endTime: TimeStamp!) {
        technicalIncidents {
            resolveTechnicalIncident(incidentId: $incidentId, endTime: $endTime)
            { id isOngoing }
        }
    }
"""

UPDATE_INCIDENT = """
    mutation ($incidentId: Int!,
              $technicalType: TechnicalIncidentTypeEnum,
              $description: String) {
        technicalIncidents {
            updateTechnicalIncident(
                incidentId: $incidentId, technicalType: $technicalType,
                description: $description
            ) { id technicalType category nature description }
        }
    }
"""

READ_INCIDENTS = """
    query {
        technicalIncidents { id technicalType category nature isOngoing }
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
        # Ongoing incident's effective end tracks "now" (uncapped).
        self.assertGreaterEqual(recent.effective_end_time, recent.start_time)

        old = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime.utcnow() - timedelta(hours=60),
        )
        self.assertTrue(old.is_ongoing)
        # Still visible up to now even after 48h, until the job closes it.
        self.assertGreater(
            old.effective_end_time,
            old.start_time + timedelta(hours=48),
        )

    def test_overlaps_date_range(self):
        day = datetime(2026, 1, 27, 8, 40)
        bounded = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=day,
            end_time=day + timedelta(hours=1),
        )
        self.assertTrue(bounded.overlaps_date_range(day.date(), day.date()))
        self.assertFalse(
            bounded.overlaps_date_range(
                (day + timedelta(days=3)).date(),
                (day + timedelta(days=3)).date(),
            )
        )

        # Ongoing incident (no end date) stays attached from its start up to
        # today, so it remains visible until manually or automatically closed.
        ongoing = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime.utcnow() - timedelta(hours=60),
        )
        start_day = ongoing.start_time.date()
        today = datetime.utcnow().date()
        self.assertTrue(ongoing.overlaps_date_range(start_day, start_day))
        self.assertTrue(ongoing.overlaps_date_range(today, today))


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
        self.assertEqual(created["category"], "infrastructure")
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
        self.assertEqual(updated["technicalType"], "AUTH_OUTAGE")
        self.assertEqual(updated["category"], "access_external")
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

    def test_resolve_sets_end_time(self):
        create = test_post_graphql_unexposed(
            CREATE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables=self._create_variables(),
        )
        incident_id = create.json["data"]["technicalIncidents"][
            "createTechnicalIncident"
        ]["id"]

        resolve = test_post_graphql_unexposed(
            RESOLVE_INCIDENT,
            mock_authentication_with_user=self.bizdev,
            variables={
                "incidentId": incident_id,
                "endTime": int(datetime(2026, 1, 27, 10, 0).timestamp()),
            },
        )
        self.assertIsNone(resolve.json.get("errors"))
        self.assertFalse(
            resolve.json["data"]["technicalIncidents"][
                "resolveTechnicalIncident"
            ]["isOngoing"]
        )


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


class TestCloseStaleIncidents(BaseTest):
    def setUp(self):
        super().setUp()
        TechnicalIncident.query.delete()
        db.session.commit()

    def test_only_incidents_older_than_delay_are_closed(self):
        recent = TechnicalIncident(
            technical_type=TechnicalIncidentType.SERVER_DOWN,
            start_time=datetime.utcnow() - timedelta(hours=2),
        )
        stale = TechnicalIncident(
            technical_type=TechnicalIncidentType.DNS_SWITCH,
            start_time=datetime.utcnow() - timedelta(hours=60),
        )
        already_closed = TechnicalIncident(
            technical_type=TechnicalIncidentType.AUTH_OUTAGE,
            start_time=datetime.utcnow() - timedelta(hours=72),
            end_time=datetime.utcnow() - timedelta(hours=70),
        )
        db.session.add_all([recent, stale, already_closed])
        db.session.commit()

        closed = TechnicalIncident.close_stale_ongoing()
        db.session.commit()

        self.assertEqual(closed, 1)
        self.assertIsNone(recent.end_time)
        self.assertEqual(
            stale.end_time, stale.start_time + timedelta(hours=48)
        )
        self.assertFalse(stale.is_ongoing)
