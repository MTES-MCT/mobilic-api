import io
import os
import zipfile
from io import BytesIO
from unittest import TestCase, expectedFailure, mock
from unittest.mock import MagicMock, patch

from app import app


def _build_zip_bomb_xlsx(decompressed_size_per_sheet):
    fp = io.BytesIO()
    custom_props = (
        '<?xml version="1.0"?><Properties>'
        '<property name="Mobilic HMAC"><lpwstr>deadbeef</lpwstr></property>'
        "</Properties>"
    )
    with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("docProps/custom.xml", custom_props)
        archive.writestr(
            "xl/worksheets/sheet1.xml", b"\0" * decompressed_size_per_sheet
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml", b"\0" * decompressed_size_per_sheet
        )
    fp.seek(0)
    return fp


class TestXlsxSignatureZipBomb(TestCase):
    @expectedFailure
    def test_verify_xlsx_signature_rejects_zip_bomb_before_processing(self):
        """AE3 [Medium] /control/verify-xlsx-signature must reject extreme compression ratios before decompressing."""
        bomb = _build_zip_bomb_xlsx(25 * 1024 * 1024)
        from app.helpers.xls import signature as signature_module

        hmac_spy = mock.Mock(wraps=signature_module.compute_hmac)
        with mock.patch.object(
            signature_module, "HMAC_KEY", b"test-key"
        ), mock.patch.object(signature_module, "compute_hmac", hmac_spy):
            app.test_client().post(
                "/control/verify-xlsx-signature",
                data={"xlsx-to-check": (bomb, "export.xlsx")},
                content_type="multipart/form-data",
            )
        self.assertFalse(
            hmac_spy.called,
            "A ~50MB payload compressed to a few KB was fully decompressed "
            "and processed: no compression-ratio guard before compute_hmac",
        )


class TestOW6ExcelFormulaInjection(TestCase):
    @expectedFailure
    def test_leading_equals_is_not_written_as_formula(self):
        """xlsx exports default strings_to_formulas=True."""
        from xlsxwriter import Workbook

        from app.helpers.xls.common import write_cells

        payload = '=1+1+cmd|" /C calc"!A0'

        class _Column:
            def lambda_style(self, resource):
                return "bold"

            def lambda_value(self, resource):
                return payload

        output = BytesIO()
        wb = Workbook(output)
        sheet = wb.add_worksheet("audit")
        write_cells(wb, sheet, [{}], 0, 0, [_Column()], None)
        wb.close()
        output.seek(0)

        with zipfile.ZipFile(output) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml")

        self.assertNotIn(
            b"<f>",
            sheet_xml,
            "Employee-controlled text starting with '=' became a live formula",
        )


class TestOW10S3PublicReadAcl(TestCase):
    @expectedFailure
    def test_upload_presigned_url_has_no_public_acl(self):
        """Control pictures uploaded with ACL public-read."""
        import app.helpers.s3 as s3_module

        fake_s3 = MagicMock()
        fake_s3.list_objects_v2.return_value = {}
        fake_s3.generate_presigned_url.return_value = "https://signed"

        with patch.object(s3_module, "S3", fake_s3):
            s3_module.S3Client.generated_presigned_urls_to_upload_picture(
                control_id=1, nb_pictures_to_upload=1
            )

        self.assertTrue(fake_s3.generate_presigned_url.called)
        _, kwargs = fake_s3.generate_presigned_url.call_args
        params = kwargs.get("Params", {})
        self.assertNotEqual(
            "public-read",
            params.get("ACL"),
            "Control picture uploads must not be world-readable",
        )


class TestOW16GrecoFilenamePathTraversal(TestCase):
    @expectedFailure
    def test_export_filename_stays_in_target_directory(self):
        """GRECO export filename path traversal (greco.py:660)."""
        import tempfile

        import app.helpers.xml.greco as greco

        parent_dir = tempfile.mkdtemp()
        base_dir = os.path.join(parent_dir, "target")
        os.makedirs(base_dir)
        sentinel = os.path.join(parent_dir, "greco_traversal_victim.xml")

        malicious_name = "../greco_traversal_victim.xml"
        previous_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            with patch.object(
                greco,
                "get_greco_xml_and_filename",
                return_value=(b"<xml/>", malicious_name),
            ):
                greco.temp_write_greco_xml(control=None)
        finally:
            os.chdir(previous_cwd)

        self.assertFalse(
            os.path.exists(sentinel),
            "A '../' in vehicle_registration_number escaped the target dir",
        )
