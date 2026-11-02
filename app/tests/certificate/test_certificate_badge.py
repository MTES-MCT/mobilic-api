import io
from datetime import date, timedelta

from PIL import Image

from app.domain.certificate import get_company_certificate_badge
from app.models.company_certification import (
    CERTIFICATION_REAL_TIME_SILVER,
    CERTIFICATION_ADMIN_CHANGES_SILVER,
    CERTIFICATION_COMPLIANCY_SILVER,
)
from app.seed import CompanyFactory
from app.seed.factories import CompanyCertificationFactory
from app.tests import BaseTest

silver_certif_args = dict(
    log_in_real_time=CERTIFICATION_REAL_TIME_SILVER,
    admin_changes=CERTIFICATION_ADMIN_CHANGES_SILVER,
    compliancy=CERTIFICATION_COMPLIANCY_SILVER,
)


class TestCertificateBadge(BaseTest):
    def setUp(self):
        super().setUp()
        self.certified_company = CompanyFactory.create(
            usual_name="certified company", siren="123456789"
        )
        self.uncertified_company = CompanyFactory.create(
            usual_name="uncertified company", siren="987654321"
        )
        CompanyCertificationFactory.create(
            company_id=self.certified_company.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=30),
            **silver_certif_args,
        )

    def test_certified_badge_is_a_saveable_png(self):
        img = get_company_certificate_badge(
            company_id=self.certified_company.id
        )

        # Renders on the real silver badge asset, not the 1x1 fallback
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(img.size, (808, 820))

        # The endpoint saves it as PNG: the result must decode back to a PNG
        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)
        reloaded = Image.open(img_io)
        self.assertEqual(reloaded.format, "PNG")
        self.assertEqual(reloaded.size, (808, 820))

    def test_uncertified_badge_is_a_blank_transparent_pixel(self):
        img = get_company_certificate_badge(
            company_id=self.uncertified_company.id
        )

        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(img.size, (1, 1))
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255, 0))
