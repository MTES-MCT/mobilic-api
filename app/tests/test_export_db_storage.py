import os
from datetime import date, datetime, time, timedelta
from io import BytesIO
from unittest.mock import patch

import openpyxl

from app import app, db
from app.helpers.celery import async_export_excel
from app.models import Export
from app.models.export import ExportStatus, ExportType
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.seed.helpers import log_and_validate_mission
from app.tests import BaseTest
from app.tests.helpers import (
    init_businesses_data,
    init_regulation_checks_data,
)

FAKE_CONTENT = b"PK\x03\x04 fake xlsx bytes"
FAKE_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FAKE_NAME = "rapport_activites.xlsx"


def post_authenticated(url, user, json=None):
    with app.test_client(
        mock_authentication_with_user=user
    ) as c, app.app_context():
        return c.post(url, json=json or {})


def get_authenticated(url, user):
    with app.test_client(
        mock_authentication_with_user=user
    ) as c, app.app_context():
        return c.get(url)


class TestExportDbStorage(BaseTest):
    def setUp(self):
        super().setUp()
        app.config["EXPORT_STORAGE_BACKEND"] = "db"
        init_businesses_data()
        init_regulation_checks_data()
        self.company = CompanyFactory.create(
            usual_name="Test Company", siren="123456789"
        )
        self.admin = UserFactory.create(email="admin@test.com")
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=self.admin,
            has_admin_rights=True,
        )
        self.other_user = UserFactory.create(email="other@test.com")

    def _ready_export(self, user=None, content=FAKE_CONTENT):
        return Export.create(
            user=user or self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.READY,
            file_content=content,
            file_name=FAKE_NAME,
            file_type=FAKE_TYPE,
            file_size=len(content) if content else 0,
        )

    @patch("app.helpers.celery.generate_admin_export_file_from_chunks")
    def test_worker_stores_file_in_db(self, mock_gen):
        mock_gen.return_value = (
            FAKE_CONTENT,
            FAKE_TYPE,
            FAKE_NAME,
            len(FAKE_CONTENT),
        )
        export = Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.WIP,
            context={},
        )
        export_id = export.id
        async_export_excel(
            self.admin.id,
            [self.company.id],
            [{"user_ids": [self.admin.id], "strategy": "single"}],
            export_id=export_id,
        )
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.READY)
        self.assertEqual(bytes(export.file_content), FAKE_CONTENT)
        self.assertEqual(export.file_size, len(FAKE_CONTENT))
        self.assertEqual(export.file_name, FAKE_NAME)
        self.assertEqual(export.file_type, FAKE_TYPE)

    def _seed_and_export(self, n_employees, n_days):
        employees = []
        for i in range(n_employees):
            emp = UserFactory.create(
                email=f"emp_{n_employees}_{n_days}_{i}@test.com"
            )
            EmploymentFactory.create(
                company=self.company,
                submitter=self.admin,
                user=emp,
                has_admin_rights=False,
            )
            employees.append(emp)

        base = date(2025, 1, 6)
        for emp in employees:
            for d in range(n_days):
                day = base + timedelta(days=d)
                log_and_validate_mission(
                    mission_name=f"m{emp.id}_{d}",
                    work_periods=[
                        [
                            datetime.combine(day, time(8, 0)),
                            datetime.combine(day, time(16, 0)),
                        ]
                    ],
                    company=self.company,
                    employee=emp,
                    admin_validating=self.admin,
                )
        db.session.commit()

        export = Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.WIP,
            context={},
        )
        export_id = export.id
        async_export_excel(
            self.admin.id,
            [self.company.id],
            [
                {
                    "user_ids": [e.id for e in employees],
                    "min_date": base.isoformat(),
                    "max_date": (base + timedelta(days=n_days)).isoformat(),
                    "file_suffix": "",
                    "strategy": "single_or_consolidated",
                }
            ],
            export_id=export_id,
        )
        db.session.expire_all()
        return Export.query.get(export_id)

    def _assert_valid_download(self, export):
        self.assertEqual(export.status, ExportStatus.READY)
        stored = bytes(export.file_content)
        self.assertTrue(stored.startswith(b"PK"))
        openpyxl.load_workbook(BytesIO(stored))
        self.assertEqual(export.file_size, len(stored))
        resp = get_authenticated(f"/exports/download/{export.id}", self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, stored)
        return len(stored)

    def test_export_small_medium_large(self):
        """Exports réels de tailles croissantes : génération -> db -> download."""
        small = self._assert_valid_download(self._seed_and_export(1, 2))
        medium = self._assert_valid_download(self._seed_and_export(5, 8))
        large = self._assert_valid_download(self._seed_and_export(15, 20))
        self.assertLess(small, medium)
        self.assertLess(medium, large)

    def test_download_handles_large_blob(self):
        """Capacité à la taille max mesurée en prod (~18 Mo) : stockage +
        download d'un contenu incompressible (comme un zip/xlsx)."""
        big = os.urandom(16 * 1024 * 1024)
        export = Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.READY,
            file_content=big,
            file_name="big.xlsx",
            file_type=FAKE_TYPE,
            file_size=len(big),
        )
        resp = get_authenticated(f"/exports/download/{export.id}", self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), len(big))
        self.assertEqual(resp.data, big)

    def test_download_marks_downloaded_and_serves_file(self):
        export = self._ready_export()
        export_id = export.id
        resp = get_authenticated(f"/exports/download/{export_id}", self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, FAKE_CONTENT)
        self.assertIn(FAKE_NAME, resp.headers.get("Content-Disposition", ""))
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.DOWNLOADED)
        self.assertIsNotNone(export.file_content)

    def test_purge_command_clears_downloaded_and_old(self):
        downloaded = Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.DOWNLOADED,
            file_content=FAKE_CONTENT,
            file_name=FAKE_NAME,
            file_type=FAKE_TYPE,
            file_size=len(FAKE_CONTENT),
        )
        ready_recent = self._ready_export()
        old_ready = self._ready_export()
        db.session.query(Export).filter(Export.id == old_ready.id).update(
            {Export.creation_time: datetime(2020, 1, 1)}
        )
        db.session.commit()
        d_id, r_id, o_id = downloaded.id, ready_recent.id, old_ready.id

        app.test_cli_runner().invoke(args=["purge_downloaded_exports"])

        db.session.expire_all()
        self.assertIsNone(Export.query.get(d_id).file_content)
        self.assertIsNone(Export.query.get(o_id).file_content)
        self.assertIsNotNone(Export.query.get(r_id).file_content)

    def test_download_404_for_other_user(self):
        export = self._ready_export()
        resp = get_authenticated(
            f"/exports/download/{export.id}", self.other_user
        )
        self.assertEqual(resp.status_code, 404)

    def test_download_404_when_no_content(self):
        export = Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.WIP,
        )
        resp = get_authenticated(f"/exports/download/{export.id}", self.admin)
        self.assertEqual(resp.status_code, 404)

    def test_checkout_returns_download_link_keeps_ready(self):
        export = self._ready_export()
        export_id = export.id
        resp = post_authenticated("/exports/checkout", self.admin)
        self.assertEqual(resp.status_code, 200)
        links = resp.json["ready_exports_links"]
        self.assertTrue(
            any(f"/api/exports/download/{export_id}" in url for url in links)
        )
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.READY)

    def test_checkout_marks_failed_when_no_content(self):
        export = self._ready_export(content=None)
        export_id = export.id
        resp = post_authenticated("/exports/checkout", self.admin)
        self.assertEqual(resp.status_code, 200)
        links = resp.json["ready_exports_links"]
        self.assertFalse(
            any(f"/exports/download/{export_id}" in url for url in links)
        )
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.FAILED)

    def _wip_export(self):
        return Export.create(
            user=self.admin,
            export_type=ExportType.EXCEL,
            status=ExportStatus.WIP,
            context={},
        )

    def _run_worker(self, export_id):
        async_export_excel(
            self.admin.id,
            [self.company.id],
            [{"user_ids": [self.admin.id], "strategy": "single"}],
            export_id=export_id,
        )

    @patch("app.helpers.celery.generate_admin_export_file_from_chunks")
    def test_worker_marks_failed_on_empty_content(self, mock_gen):
        mock_gen.return_value = (b"", FAKE_TYPE, FAKE_NAME, 0)
        export_id = self._wip_export().id
        with self.assertRaisesRegex(ValueError, "empty content"):
            self._run_worker(export_id)
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.FAILED)
        self.assertIsNone(export.file_content)

    @patch("app.helpers.celery.generate_admin_export_file_from_chunks")
    def test_worker_marks_failed_on_oversize_content(self, mock_gen):
        self.addCleanup(app.config.pop, "EXPORT_DB_MAX_SIZE_MB", None)
        app.config["EXPORT_DB_MAX_SIZE_MB"] = 1
        big = b"x" * (2 * 1024 * 1024)
        mock_gen.return_value = (big, FAKE_TYPE, FAKE_NAME, len(big))
        export_id = self._wip_export().id
        with self.assertRaisesRegex(ValueError, "too large for db storage"):
            self._run_worker(export_id)
        db.session.expire_all()
        export = Export.query.get(export_id)
        self.assertEqual(export.status, ExportStatus.FAILED)
        self.assertIsNone(export.file_content)

    def test_alert_stuck_exports(self):
        export_id = self._wip_export().id
        with patch.object(app.logger, "error") as mock_err:
            app.test_cli_runner().invoke(args=["alert_stuck_exports"])
        self.assertFalse(mock_err.called)

        db.session.query(Export).filter(Export.id == export_id).update(
            {Export.creation_time: datetime(2020, 1, 1)}
        )
        db.session.commit()
        with patch.object(app.logger, "error") as mock_err:
            app.test_cli_runner().invoke(args=["alert_stuck_exports"])
        self.assertTrue(mock_err.called)
