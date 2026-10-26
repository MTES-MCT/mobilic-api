from app import db
from app.domain.vehicle import (
    canonicalize_registration_number,
    find_or_create_vehicle,
    find_vehicle,
)
from app.helpers.errors import InvalidParamsError
from app.models import Vehicle
from app.seed import CompanyFactory
from app.seed.factories import VehicleFactory
from app.tests import BaseTest


class TestVehicleRegistrationNumber(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()

    def test_canonicalize_strips_separators_and_uppercases(self):
        self.assertEqual(
            canonicalize_registration_number("ab-123-cd"), "AB123CD"
        )
        self.assertEqual(
            canonicalize_registration_number("6184 0001"), "61840001"
        )

    def test_create_stores_canonical_form(self):
        vehicle = find_or_create_vehicle(
            company_id=self.company.id,
            vehicle_registration_number="ab-123-cd",
        )
        db.session.flush()
        self.assertEqual(vehicle.registration_number, "AB123CD")

    def test_military_plate_is_stored_without_space(self):
        vehicle = find_or_create_vehicle(
            company_id=self.company.id,
            vehicle_registration_number="6184 0001",
        )
        db.session.flush()
        self.assertEqual(vehicle.registration_number, "61840001")

    def test_matches_legacy_vehicle_stored_with_separators(self):
        legacy = VehicleFactory.create(
            company_id=self.company.id,
            registration_number="AB-123-CD",
        )
        found = find_vehicle("ab 123 cd", self.company.id)
        self.assertEqual([v.id for v in found], [legacy.id])

    def test_same_plate_different_format_is_not_duplicated(self):
        first = find_or_create_vehicle(
            company_id=self.company.id,
            vehicle_registration_number="AB-123-CD",
        )
        db.session.flush()
        second = find_or_create_vehicle(
            company_id=self.company.id,
            vehicle_registration_number="ab 123 cd",
        )
        db.session.flush()
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.registration_number, "AB123CD")
        self.assertEqual(
            Vehicle.query.filter(
                Vehicle.company_id == self.company.id
            ).count(),
            1,
        )

    def test_registration_number_with_only_separators_is_rejected(self):
        for value in ["", "   ", "---", " - - "]:
            with self.assertRaises(InvalidParamsError):
                find_or_create_vehicle(
                    company_id=self.company.id,
                    vehicle_registration_number=value,
                )
        self.assertEqual(
            Vehicle.query.filter(
                Vehicle.company_id == self.company.id
            ).count(),
            0,
        )

    def test_like_wildcards_do_not_match_other_vehicles(self):
        find_or_create_vehicle(
            company_id=self.company.id,
            vehicle_registration_number="AB-123-CD",
        )
        db.session.flush()
        self.assertEqual(
            find_vehicle("A%23CD", self.company.id),
            [],
        )
        self.assertEqual(
            find_vehicle("A_123CD", self.company.id),
            [],
        )
        self.assertEqual(
            len(find_vehicle("ab 123 cd", self.company.id)),
            1,
        )
